"""
Tests for the analytics endpoints.
"""
import pytest


async def test_summary_endpoint(client, seeded_db):
    """Test that the summary KPIs are calculated correctly."""
    response = await client.get("/analytics/summary")
    assert response.status_code == 200
    data = response.json()

    # Our seeded data has exactly 3 orders, 2 customers, 2 products
    # Total revenue = 40 + 10 + 100 = 150
    assert data["total_orders"] == 3
    assert data["total_customers"] == 2
    assert data["total_products"] == 2
    assert data["total_revenue"] == "150.0"
    
    # Average order value = 150 / 3 = 50.0
    assert data["average_order_value"] == "50.0"


async def test_top_products_endpoint(client, seeded_db):
    """
    Test that products are ranked by revenue correctly.
    'Expensive Item' made 120 (1x20 + 5x20), 'Cheap Item' made 30 (2x10 + 1x10).
    """
    response = await client.get("/analytics/top-products?limit=5")
    assert response.status_code == 200
    data = response.json()

    # The most expensive/revenue-generating product should be first
    assert len(data) == 2
    assert data[0]["product_name"] == "Expensive Item"
    assert data[0]["total_revenue"] == "120.0"
    assert data[0]["total_quantity"] == 6

    assert data[1]["product_name"] == "Cheap Item"
    assert data[1]["total_revenue"] == "30.0"
    assert data[1]["total_quantity"] == 3


async def test_category_performance_endpoint(client, seeded_db):
    """Test that revenue is grouped by category correctly."""
    response = await client.get("/analytics/category-performance")
    assert response.status_code == 200
    data = response.json()

    # Both products belong to the "Test" category
    assert len(data) == 1
    assert data[0]["category"] == "Test"
    assert data[0]["revenue"] == "150.0"
    assert data[0]["items_sold"] == 9  # Total quantity of all items