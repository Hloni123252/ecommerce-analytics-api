"""
ML endpoints: churn model training and prediction.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.ml.features import build_customer_features
from app.ml.predictor import (
    train_model,
    predict_batch,
    is_model_trained,
)
from app.schemas.ml import TrainResponse, BatchChurnResponse, ChurnPrediction


router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/train", response_model=TrainResponse)
async def train_churn_model(db: AsyncSession = Depends(get_db)):
    """
    Train the churn prediction model on current order data.
    
    Runs synchronously. On large datasets, call this via Celery.
    """
    df = await build_customer_features(db)
    result = train_model(df)
    return {"status": "trained", **result}


@router.get("/churn", response_model=BatchChurnResponse)
async def predict_all(
    limit: int = Query(20, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Predict churn for all customers, return the top N at-risk ones.
    """
    if not is_model_trained():
        raise HTTPException(
            status_code=400,
            detail="Model not trained yet. Call POST /ml/train first.",
        )

    df = await build_customer_features(db)
    df = df[df["total_orders"] > 0]  # only customers with history

    df = predict_batch(df)

    # Aggregate
    high = int((df["risk_level"] == "high").sum())
    medium = int((df["risk_level"] == "medium").sum())
    low = int((df["risk_level"] == "low").sum())

    # Top at-risk
    top = df.sort_values("churn_probability", ascending=False).head(limit)

    return {
        "total_customers": len(df),
        "high_risk_count": high,
        "medium_risk_count": medium,
        "low_risk_count": low,
        "top_at_risk": [
            {
                "customer_id": int(r.customer_id),
                "churn_probability": float(r.churn_probability),
                "risk_level": r.risk_level,
            }
            for r in top.itertuples()
        ],
    }


@router.get("/churn/{customer_id}", response_model=ChurnPrediction)
async def predict_one(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Predict churn for a single customer."""
    if not is_model_trained():
        raise HTTPException(
            status_code=400,
            detail="Model not trained yet. Call POST /ml/train first.",
        )

    df = await build_customer_features(db)
    customer_row = df[df["customer_id"] == customer_id]

    if customer_row.empty:
        raise HTTPException(status_code=404, detail="Customer not found")

    result = predict_batch(customer_row).iloc[0]
    return {
        "customer_id": int(result["customer_id"]),
        "churn_probability": float(result["churn_probability"]),
        "risk_level": result["risk_level"],
    }