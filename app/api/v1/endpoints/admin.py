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
SEED_SECRET = "deploy-once-12345"

# Batch sizes — keep SQL statements small
CUSTOMER_BATCH = 100
PRODUCT_BATCH = 100
ORDER_BATCH = 500
ITEM_BATCH = 1000


def _chunks(items: list, size: int):
    """Yield successive chunks of a list."""
    for i in range(0, len(items), size):
        yield items[i:i + size]


@router.post("/recompute")
def trigger_recompute():
    """Trigger a background recomputation of analytics cache."""
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
    secret: str = Query(..., description="Shared secret"),
    customers: int = Query(500, ge=1, le=2000),
    products: int = Query(200, ge=1, le=1000),
    orders: int = Query(10000, ge=100, le=50000),
):
    """
    Seed the database with fake data (batched inserts to avoid connection timeouts).
    """
    if secret != SEED_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    from scripts.seed_data import (
        generate_customers,
        generate_products,
        generate_orders_and_items,
    )
    from app.core.database import AsyncSessionLocal
    from app.models import Customer, Product, Order, OrderItem
    from sqlalchemy import insert, func, update

    # ---- Generate all data first (no DB) ----
    customers_df = generate_customers()
    products_df = generate_products()

    async with AsyncSessionLocal() as session:
        # ---- 1. Insert customers in batches ----
        customer_ids = []
        customer_records = customers_df.to_dict(orient="records")
        for batch in _chunks(customer_records, CUSTOMER_BATCH):
            result = await session.execute(
                insert(Customer).returning(Customer.id), batch
            )
            customer_ids.extend([row[0] for row in result.fetchall()])
            await session.commit()

        # ---- 2. Insert products in batches ----
        product_ids = []
        product_records = products_df.to_dict(orient="records")
        for batch in _chunks(product_records, PRODUCT_BATCH):
            result = await session.execute(
                insert(Product).returning(Product.id), batch
            )
            product_ids.extend([row[0] for row in result.fetchall()])
            await session.commit()

        # Build product id/price lookup
        product_data = [
            {"id": pid, "price": float(products_df.iloc[i]["price"])}
            for i, pid in enumerate(product_ids)
        ]

        # ---- 3. Generate orders + items (no DB) ----
        orders_df, items_df = generate_orders_and_items(customer_ids, product_data)

        # ---- 4. Insert orders in batches ----
        order_ids = []
        order_records = orders_df.drop(columns=["temp_id"]).to_dict(orient="records")
        for batch in _chunks(order_records, ORDER_BATCH):
            result = await session.execute(
                insert(Order).returning(Order.id), batch
            )
            order_ids.extend([row[0] for row in result.fetchall()])
            await session.commit()

        # ---- 5. Insert order items in batches ----
        temp_to_real = {i: order_ids[i] for i in range(len(order_ids))}
        items_df["order_id"] = items_df["order_temp_id"].map(temp_to_real)
        items_df["unit_price"] = items_df["unit_price"].astype(float)

        items_records = items_df[
            ["order_id", "product_id", "quantity", "unit_price"]
        ].to_dict(orient="records")

        total_items = 0
        for batch in _chunks(items_records, ITEM_BATCH):
            await session.execute(insert(OrderItem), batch)
            await session.commit()
            total_items += len(batch)

        # ---- 6. Compute totals in one SQL statement (fast) ----
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
        "items": total_items,
    }