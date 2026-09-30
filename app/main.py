from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.database import engine, Base

# Import models so they register with Base.metadata
from app.models import Customer, Product, Order, OrderItem, AnalyticsCache  # noqa: F401

# Import routers
from app.api.v1.endpoints import analytics, admin, ml


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created (or already exist)")
    yield
    await engine.dispose()
    print("✅ Database connection closed")


app = FastAPI(
    title="E-Commerce Analytics API",
    version="0.1.0",
    description="Analytics platform with FastAPI, Celery, Redis, and ML",
    lifespan=lifespan,
)

app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(ml.router)


@app.get("/")
async def root():
    return {"message": "E-Commerce Analytics API is running", "status": "healthy"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}