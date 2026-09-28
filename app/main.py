from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.core.database import engine, Base

# Import models so they register with Base.metadata
from app.models import Customer, Product, Order, OrderItem  # noqa: F401


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


@app.get("/")
async def root():
    return {"message": "E-Commerce Analytics API is running", "status": "healthy"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}