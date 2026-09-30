from pydantic import BaseModel
from typing import Dict, List


class TrainingMetrics(BaseModel):
    accuracy: float
    precision: float
    recall: float
    training_rows: int
    churn_rate: float


class TrainResponse(BaseModel):
    status: str
    metrics: TrainingMetrics
    feature_importance: Dict[str, float]


class ChurnPrediction(BaseModel):
    customer_id: int
    churn_probability: float
    risk_level: str


class BatchChurnResponse(BaseModel):
    total_customers: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    top_at_risk: List[ChurnPrediction]