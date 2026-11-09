"""
Pytest fixtures for the E-Commerce Analytics API.
"""
import os
from datetime import datetime, timezone, timedelta

# 1. SET ENVIRONMENT VARIABLES FIRST
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_ecom.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/1"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/2"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models import Customer, Product, Order, OrderItem

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

# -------------------------------------------------------------------
# FIXTURE 1: For Analytics Tests (Exact Math)
# -------------------------------------------------------------------
@pytest_asyncio.fixture
async def seeded_db(db_session):
    """Insert a predictable dataset for analytics tests."""
    now = datetime.now(timezone.utc)

    c1 = Customer(email="active@test.com", full_name="Active User", country="ZA", created_at=now - timedelta(days=100))
    c2 = Customer(email="churn@test.com", full_name="Churned User", country="ZA", created_at=now - timedelta(days=200))
    db_session.add_all([c1, c2])
    await db_session.commit()

    p1 = Product(name="Cheap Item", category="Test", price=10.0, stock=100)
    p2 = Product(name="Expensive Item", category="Test", price=20.0, stock=50)
    db_session.add_all([p1, p2])
    await db_session.commit()

    o1 = Order(customer_id=c1.id, status="delivered", total_amount=40.0, created_at=now)
    o2 = Order(customer_id=c1.id, status="delivered", total_amount=10.0, created_at=now - timedelta(days=10))
    o3 = Order(customer_id=c2.id, status="delivered", total_amount=100.0, created_at=now - timedelta(days=150))
    db_session.add_all([o1, o2, o3])
    await db_session.commit()

    items = [
        OrderItem(order_id=o1.id, product_id=p1.id, quantity=2, unit_price=10.0),
        OrderItem(order_id=o1.id, product_id=p2.id, quantity=1, unit_price=20.0),
        OrderItem(order_id=o2.id, product_id=p1.id, quantity=1, unit_price=10.0),
        OrderItem(order_id=o3.id, product_id=p2.id, quantity=5, unit_price=20.0),
    ]
    db_session.add_all(items)
    await db_session.commit()

    return {"c1": c1, "c2": c2, "p1": p1, "p2": p2}

# -------------------------------------------------------------------
# FIXTURE 2: For ML Tests (Larger Dataset)
# -------------------------------------------------------------------
@pytest_asyncio.fixture
async def seeded_ml_db(db_session):
    """Insert a larger dataset for ML training so train_test_split doesn't crash."""
    now = datetime.now(timezone.utc)
    
    for i in range(20):
        c = Customer(
            email=f"ml_test_{i}@test.com", 
            full_name=f"ML User {i}", 
            country="ZA", 
            created_at=now - timedelta(days=200)
        )
        db_session.add(c)
        await db_session.commit()
        
        o_past = Order(
            customer_id=c.id, status="delivered", total_amount=50.0, 
            created_at=now - timedelta(days=120)
        )
        db_session.add(o_past)
        
        if i % 2 == 0:
            o_recent = Order(
                customer_id=c.id, status="delivered", total_amount=30.0, 
                created_at=now - timedelta(days=10)
            )
            db_session.add(o_recent)
            
    await db_session.commit()