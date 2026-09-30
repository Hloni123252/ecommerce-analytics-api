"""
Feature engineering for churn prediction.

Uses a TIME-BASED SPLIT to prevent data leakage:
- Features come from BEFORE a cutoff date (the past)
- Label comes from AFTER the cutoff date (the future)

This forces the model to learn from past behavior to predict future behavior.
"""
import pandas as pd
from datetime import datetime, timezone, timedelta
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

# Configuration
FEATURE_WINDOW_DAYS = 365   # Features come from orders within this window
LABEL_WINDOW_DAYS = 90      # Churn = no order in this window after cutoff


def _compute_derived_features(df: pd.DataFrame, reference_date: datetime) -> pd.DataFrame:
    """Compute feature columns relative to a reference date."""
    df["days_as_customer"] = (
        reference_date - pd.to_datetime(df["customer_created"], utc=True)
    ).dt.days.clip(lower=1)

    df["days_since_last_order"] = (
        reference_date - pd.to_datetime(df["last_order_date"], utc=True)
    ).dt.days
    df["days_since_last_order"] = df["days_since_last_order"].fillna(9999)

    df["avg_order_value"] = df["total_spent"] / df["total_orders"].clip(lower=1)
    df["order_frequency"] = (
        df["total_orders"] / df["days_as_customer"].clip(lower=1) * 30
    )
    return df


async def build_training_features(db: AsyncSession) -> pd.DataFrame:
    """
    Build training data with a time split.

    Cutoff = now - LABEL_WINDOW_DAYS
    Features = computed from orders BEFORE cutoff
    Label = 1 if no order AFTER cutoff, else 0
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=LABEL_WINDOW_DAYS)
    feature_window_start = cutoff - timedelta(days=FEATURE_WINDOW_DAYS)

    # --- Past: aggregate orders before cutoff ---
    past_query = (
        select(
            Customer.id.label("customer_id"),
            Customer.created_at.label("customer_created"),
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total_amount), 0).label("total_spent"),
            func.max(Order.created_at).label("last_order_date"),
        )
        .outerjoin(
            Order,
            (Customer.id == Order.customer_id)
            & (Order.created_at < cutoff)
            & (Order.created_at >= feature_window_start),
        )
        .group_by(Customer.id, Customer.created_at)
    )
    past_rows = (await db.execute(past_query)).all()

    # --- Future: count orders after cutoff (the label signal) ---
    future_query = (
        select(
            Customer.id.label("customer_id"),
            func.count(Order.id).label("orders_after_cutoff"),
        )
        .outerjoin(
            Order,
            (Customer.id == Order.customer_id) & (Order.created_at >= cutoff),
        )
        .group_by(Customer.id)
    )
    future_rows = (await db.execute(future_query)).all()
    future_map = {r.customer_id: int(r.orders_after_cutoff or 0) for r in future_rows}

    # --- Assemble DataFrame ---
    records = []
    for r in past_rows:
        records.append({
            "customer_id": r.customer_id,
            "customer_created": r.customer_created,
            "total_orders": int(r.total_orders or 0),
            "total_spent": float(r.total_spent or 0),
            "last_order_date": r.last_order_date,
            "orders_after_cutoff": future_map.get(r.customer_id, 0),
        })

    df = pd.DataFrame(records)

    # Only keep customers who existed before the cutoff
    df = df[pd.to_datetime(df["customer_created"], utc=True) < cutoff].copy()

    # Compute features relative to cutoff
    df = _compute_derived_features(df, cutoff)

    # Label: churned if had orders before cutoff AND no orders after
    df["churned"] = (
        (df["total_orders"] > 0) & (df["orders_after_cutoff"] == 0)
    ).astype(int)

    return df


async def build_prediction_features(db: AsyncSession) -> pd.DataFrame:
    """
    Build features for ALL current customers using data up to now.

    Used at inference time to score everyone.
    """
    now = datetime.now(timezone.utc)
    feature_window_start = now - timedelta(days=FEATURE_WINDOW_DAYS)

    query = (
        select(
            Customer.id.label("customer_id"),
            Customer.created_at.label("customer_created"),
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total_amount), 0).label("total_spent"),
            func.max(Order.created_at).label("last_order_date"),
        )
        .outerjoin(
            Order,
            (Customer.id == Order.customer_id)
            & (Order.created_at >= feature_window_start),
        )
        .group_by(Customer.id, Customer.created_at)
    )
    rows = (await db.execute(query)).all()

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
    df = _compute_derived_features(df, now)
    return df