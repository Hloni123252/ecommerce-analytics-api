"""
Seed the e-commerce database with realistic fake data.

Usage:
    poetry run python -m scripts.seed_data

Generates:
    - 500 customers
    - 200 products
    - 10,000 orders with 1-4 items each
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone

import pandas as pd
from faker import Faker
from sqlalchemy import insert, update, func

from app.core.database import AsyncSessionLocal
from app.models import Customer, Product, Order, OrderItem

fake = Faker()

# ---------- Config ----------
NUM_CUSTOMERS = 500
NUM_PRODUCTS = 200
NUM_ORDERS = 10_000

CATEGORIES = [
    "Electronics", "Clothing", "Books", "Home", "Sports",
    "Toys", "Beauty", "Food", "Automotive", "Garden",
]

COUNTRIES = [
    "South Africa", "USA", "UK", "Germany", "France",
    "Canada", "Australia", "Nigeria", "Kenya", "India",
]

ORDER_STATUSES = ["pending", "paid", "shipped", "delivered", "cancelled"]


# ---------- Generators ----------
def generate_customers() -> pd.DataFrame:
    """Generate NUM_CUSTOMERS customers."""
    customers = []
    for _ in range(NUM_CUSTOMERS):
        customers.append({
            "email": fake.unique.email(),
            "full_name": fake.name(),
            "country": random.choice(COUNTRIES),
            "created_at": fake.date_time_between(
                start_date="-2y", end_date="now", tzinfo=timezone.utc
            ),
        })
    return pd.DataFrame(customers)


def generate_products() -> pd.DataFrame:
    """Generate NUM_PRODUCTS products."""
    products = []
    for _ in range(NUM_PRODUCTS):
        category = random.choice(CATEGORIES)
        products.append({
            "name": f"{fake.word().title()} {category[:-1] if category.endswith('s') else category}",
            "category": category,
            "price": round(random.uniform(5.0, 500.0), 2),
            "stock": random.randint(0, 500),
            "created_at": fake.date_time_between(
                start_date="-1y", end_date="now", tzinfo=timezone.utc
            ),
        })
    return pd.DataFrame(products)


def generate_orders_and_items(
    customer_ids: list[int], product_data: list[dict]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate orders and their items.
    
    product_data is a list of dicts with id and price.
    """
    orders = []
    items = []

    # Realistic: some customers order a lot, some rarely
    customer_weights = [random.random() ** 2 for _ in customer_ids]

    for i in range(NUM_ORDERS):
        # Pick a customer (weighted — some are more active)
        customer_id = random.choices(customer_ids, weights=customer_weights, k=1)[0]

        # Order date in last 12 months
        days_ago = random.randint(0, 365)
        order_date = datetime.now(timezone.utc) - timedelta(days=days_ago)

        status = random.choices(
            ORDER_STATUSES,
            weights=[10, 25, 20, 40, 5],  # Most delivered
            k=1,
        )[0]

        order_row = {
            "customer_id": customer_id,
            "status": status,
            "created_at": order_date,
            "temp_id": i,  # used later to link items
        }
        orders.append(order_row)

        # 1-4 items per order
        num_items = random.randint(1, 4)
        # Sample without replacement so no duplicate products per order
        chosen_products = random.sample(product_data, num_items)

        for p in chosen_products:
            quantity = random.randint(1, 5)
            items.append({
                "order_temp_id": i,
                "product_id": p["id"],
                "quantity": quantity,
                "unit_price": p["price"],
            })

    return pd.DataFrame(orders), pd.DataFrame(items)


# ---------- Analysis ----------
def analyze_data(customers: pd.DataFrame, products: pd.DataFrame,
                 orders: pd.DataFrame, items: pd.DataFrame) -> None:
    """Print quick analysis using Pandas."""
    print("\n📊 Data Analysis:")
    print(f"   Customers:       {len(customers)}")
    print(f"   Products:        {len(products)}")
    print(f"   Orders:          {len(orders)}")
    print(f"   Order Items:     {len(items)}")
    print(f"   Avg items/order: {len(items) / len(orders):.2f}")
    print(f"\n   Top 5 categories (products):")
    for cat, count in products["category"].value_counts().head(5).items():
        print(f"      {cat}: {count}")
    print(f"\n   Order status distribution:")
    for status, count in orders["status"].value_counts().items():
        pct = count / len(orders) * 100
        print(f"      {status}: {count} ({pct:.1f}%)")


# ---------- Seeding ----------
async def seed():
    print("🌱 Starting seed process...\n")

    async with AsyncSessionLocal() as session:
        # ---------- 1. Customers ----------
        print("👥 Generating customers...")
        customers_df = generate_customers()

        result = await session.execute(
            insert(Customer).returning(Customer.id),
            customers_df.to_dict(orient="records"),
        )
        customer_ids = [row[0] for row in result.fetchall()]
        await session.commit()
        print(f"   ✅ Inserted {len(customer_ids)} customers")

        # ---------- 2. Products ----------
        print("\n📦 Generating products...")
        products_df = generate_products()

        result = await session.execute(
            insert(Product).returning(Product.id),
            products_df.to_dict(orient="records"),
        )
        product_ids = [row[0] for row in result.fetchall()]
        await session.commit()
        print(f"   ✅ Inserted {len(product_ids)} products")

        # Build a lookup: product_id -> price (for order items)
        product_data = [
            {"id": pid, "price": float(products_df.iloc[i]["price"])}
            for i, pid in enumerate(product_ids)
        ]

        # ---------- 3. Orders ----------
        print("\n🛒 Generating orders and items...")
        orders_df, items_df = generate_orders_and_items(customer_ids, product_data)
        print(f"   Generated {len(orders_df)} orders and {len(items_df)} items")

        # Insert orders (drop temp_id first)
        orders_to_insert = orders_df.drop(columns=["temp_id"]).to_dict(orient="records")
        result = await session.execute(
            insert(Order).returning(Order.id),
            orders_to_insert,
        )
        order_ids = [row[0] for row in result.fetchall()]
        await session.commit()
        print(f"   ✅ Inserted {len(order_ids)} orders")

        # ---------- 4. Order Items ----------
        # Map temp_id -> real order id
        temp_to_real = {i: order_ids[i] for i in range(len(order_ids))}
        items_df["order_id"] = items_df["order_temp_id"].map(temp_to_real)
        items_df["unit_price"] = items_df["unit_price"].astype(float)

        items_to_insert = items_df[
            ["order_id", "product_id", "quantity", "unit_price"]
        ].to_dict(orient="records")

        await session.execute(insert(OrderItem), items_to_insert)
        await session.commit()
        print(f"   ✅ Inserted {len(items_to_insert)} order items")

        # ---------- 5. Update order totals ----------
        print("\n💰 Computing order totals...")
        # Sum quantity * unit_price per order, then update orders
        totals_result = await session.execute(
            select_totals_query()
        )
        for order_id, total in totals_result.fetchall():
            await session.execute(
                update(Order).where(Order.id == order_id).values(total_amount=total)
            )
        await session.commit()
        print(f"   ✅ Updated totals for all orders")

    # ---------- Analysis ----------
    analyze_data(customers_df, products_df, orders_df, items_df)

    print("\n🎉 Seeding complete!\n")


def select_totals_query():
    """Helper: query to aggregate order totals."""
    from sqlalchemy import select
    return (
        select(
            OrderItem.order_id,
            func.sum(OrderItem.quantity * OrderItem.unit_price).label("total"),
        )
        .group_by(OrderItem.order_id)
    )


if __name__ == "__main__":
    asyncio.run(seed())