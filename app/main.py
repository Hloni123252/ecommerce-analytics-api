from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from app.core.database import engine, Base

# Import models so they register with Base.metadata
from app.models import Customer, Product, Order, OrderItem, AnalyticsCache  # noqa: F401

# Import routers
from app.api.v1.endpoints import analytics, admin, ml


async def _create_tables_background():
    """Run table creation in the background so startup isn't blocked."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created (or already exist)")
    except Exception as e:
        print(f"⚠️  Table creation failed (may already exist): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Kick off table creation as a background task.
    # The app can accept traffic immediately while this runs.
    task = asyncio.create_task(_create_tables_background())
    yield
    task.cancel()
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