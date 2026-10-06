"""
Admin endpoints: trigger background tasks, inspect cache, seed data.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.database import get_db
from app.models.analytics_cache import AnalyticsCache
from app.tasks.analytics_tasks import recompute_analytics


router = APIRouter(prefix="/admin", tags=["admin"])


# Simple shared secret to prevent randoms from triggering a seed.
# Not real security — just a footgun guard.
SEED_SECRET = "deploy-once-12345"


@router.post("/recompute")
def trigger_recompute():
    """
    Trigger a background recomputation of analytics cache.
    """
    task = recompute_analytics.delay()
    return {"task_id": task.id, "status": "queued"}


@router.get("/cache")
async def list_cache(db: AsyncSession = Depends(get_db)):
    """List all cached analytics entries."""
    result = await db.execute(
        select(AnalyticsCache).order_by(AnalyticsCache.key)
    )
    rows = result.scalars().all()

    return [
        {
            "key": row.key,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "preview": json.loads(row.value) if row.key == "summary" else "[cached]",
        }
        for row in rows
    ]


@router.post("/seed")
async def seed_database_endpoint(
    secret: str = Query(..., description="Shared secret to prevent unauthorized seeding"),
    customers: int = Query(500, ge=1, le=2000),
    products: int = Query(200, ge=1, le=1000),
    orders: int = Query(10000, ge=100, le=50000),
):
    """
    Seed the database with fake data.
    
    One-time use endpoint for demo deployments.
    In a real system, this would be protected by admin auth.
    
    ⚠️ This endpoint should be REMOVED after seeding.
    """
    if secret != SEED_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    # Import here so seeder isn't loaded on every request
    from scripts.seed_data import (
        generate_customers,
        generate_products,
        generate_orders_and_items,
    )
    from app.core.database import AsyncSessionLocal
    from app.models import Customer, Product, Order, OrderItem
    from sqlalchemy import insert, func, update

    async with AsyncSessionLocal() as session:
        # 1. Customers
        customers_df = generate_customers()
        result = await session.execute(
            insert(Customer).returning(Customer.id),
            customers_df.to_dict(orient="records"),
        )
        customer_ids = [row[0] for row in result.fetchall()]
        await session.commit()

        # 2. Products
        products_df = generate_products()
        result = await session.execute(
            insert(Product).returning(Product.id),
            products_df.to_dict(orient="records"),
        )
        product_ids = [row[0] for row in result.fetchall()]
        await session.commit()

        product_data = [
            {"id": pid, "price": float(products_df.iloc[i]["price"])}
            for i, pid in enumerate(product_ids)
        ]

        # 3. Orders + items
        orders_df, items_df = generate_orders_and_items(customer_ids, product_data)

        orders_to_insert = orders_df.drop(columns=["temp_id"]).to_dict(orient="records")
        result = await session.execute(
            insert(Order).returning(Order.id),
            orders_to_insert,
        )
        order_ids = [row[0] for row in result.fetchall()]
        await session.commit()

        temp_to_real = {i: order_ids[i] for i in range(len(order_ids))}
        items_df["order_id"] = items_df["order_temp_id"].map(temp_to_real)
        items_df["unit_price"] = items_df["unit_price"].astype(float)

        items_to_insert = items_df[
            ["order_id", "product_id", "quantity", "unit_price"]
        ].to_dict(orient="records")
        await session.execute(insert(OrderItem), items_to_insert)
        await session.commit()

        # 4. Compute totals with a single SQL update (fast)
        await session.execute(
            update(Order).values(
                total_amount=select(
                    func.coalesce(
                        func.sum(OrderItem.quantity * OrderItem.unit_price), 0
                    )
                )
                .where(OrderItem.order_id == Order.id)
                .scalar_subquery()
            )
        )
        await session.commit()

    return {
        "status": "seeded",
        "customers": len(customer_ids),
        "products": len(product_ids),
        "orders": len(order_ids),
        "items": len(items_to_insert),
    }