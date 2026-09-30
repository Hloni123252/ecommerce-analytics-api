"""
Feature engineering for churn prediction.

Transforms raw orders into per-customer feature vectors.
"""
import pandas as pd
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import Customer, Order


FEATURE_COLUMNS = [
    "days_as_customer",
    "total_orders",
    "total_spent",
    "avg_order_value",
    "order_frequency",
    "days_since_last_order",
]


async def build_customer_features(db: AsyncSession) -> pd.DataFrame:
    """
    Build a pandas DataFrame with one row per customer.
    
    Columns: customer_id + feature columns + churned label.
    """
    now = datetime.now(timezone.utc)

    # Aggregate orders per customer
    query = (
        select(
            Customer.id.label("customer_id"),
            Customer.created_at.label("customer_created"),
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total_amount), 0).label("total_spent"),
            func.max(Order.created_at).label("last_order_date"),
        )
        .outerjoin(Order, Customer.id == Order.customer_id)
        .group_by(Customer.id, Customer.created_at)
    )

    result = await db.execute(query)
    rows = result.all()

    # Convert to DataFrame
    records = []
    for r in rows:
        records.append({
            "customer_id": r.customer_id,
            "customer_created": r.customer_created,
            "total_orders": int(r.total_orders or 0),
            "total_spent": float(r.total_spent or 0),
            "last_order_date": r.last_order_date,
        })

    df = pd.DataFrame(records)

    # Derived features
    df["days_as_customer"] = (now - pd.to_datetime(df["customer_created"], utc=True)).dt.days.clip(lower=1)
    df["days_since_last_order"] = (
        now - pd.to_datetime(df["last_order_date"], utc=True)
    ).dt.days

    # Customers with no orders: days_since_last_order is NaN → give them a large value
    df["days_since_last_order"] = df["days_since_last_order"].fillna(9999)

    df["avg_order_value"] = df["total_spent"] / df["total_orders"].clip(lower=1)
    df["order_frequency"] = df["total_orders"] / df["days_as_customer"].clip(lower=1) * 30

    # Label: churned if no order in last 90 days BUT had at least 1 order ever
    df["churned"] = (
        (df["days_since_last_order"] > 90) & (df["total_orders"] > 0)
    ).astype(int)

    return df