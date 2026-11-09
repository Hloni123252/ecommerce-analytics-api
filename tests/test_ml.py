"""
Tests for the ML churn prediction endpoints.
"""
import pytest

async def test_train_model(client, seeded_ml_db):
    """Test that the model trains successfully on the seeded data."""
    response = await client.post("/ml/train")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "trained"
    
    # Check that metrics were returned
    metrics = data["metrics"]
    assert "accuracy" in metrics
    assert metrics["training_rows"] > 0
    
    # Check that feature importance was calculated
    importance = data["feature_importance"]
    assert "days_since_last_order" in importance

async def test_get_batch_churn_predictions(client, seeded_ml_db):
    """Test the batch churn prediction endpoint."""
    await client.post("/ml/train")
    
    response = await client.get("/ml/churn?limit=5")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total_customers"] == 20
    
    total_risk = data["high_risk_count"] + data["medium_risk_count"] + data["low_risk_count"]
    assert total_risk == 20
    
    assert len(data["top_at_risk"]) == 5

async def test_get_single_churn_prediction(client, seeded_ml_db):
    """Test the prediction endpoint for a single customer."""
    await client.post("/ml/train")
    
    response = await client.get("/ml/churn/1")
    assert response.status_code == 200
    
    data = response.json()
    assert data["customer_id"] == 1
    assert 0.0 <= data["churn_probability"] <= 1.0
    assert data["risk_level"] in ["low", "medium", "high"]

async def test_get_single_churn_prediction_not_found(client, seeded_ml_db):
    """Test that a 404 is returned for an invalid customer ID."""
    await client.post("/ml/train")
    
    response = await client.get("/ml/churn/99999")
    assert response.status_code == 404
    assert "Customer not found" in response.json()["detail"]