"""
Celery tasks for analytics precomputation.

The task refreshes cached analytics so endpoints serve them instantly.
"""
import asyncio
import json

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.repositories.analytics_repository import AnalyticsRepository
from app.models.analytics_cache import AnalyticsCache
from sqlalchemy import select


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Eager mode inside FastAPI's event loop — use a new thread-safe task
        return asyncio.run(coro)
    return asyncio.run(coro)


async def _recompute_summary_async() -> dict:
    """Recompute summary + top products, store both in the cache table."""
    async with AsyncSessionLocal() as session:
        # Compute
        summary = await AnalyticsRepository.get_summary(session)
        top_products = await AnalyticsRepository.get_top_products(session, limit=10)
        categories = await AnalyticsRepository.get_category_performance(session)

        # Store in cache table
        for key, value in [
            ("summary", summary),
            ("top_products", top_products),
            ("categories", categories),
        ]:
            existing = await session.execute(
                select(AnalyticsCache).where(AnalyticsCache.key == key)
            )
            row = existing.scalar_one_or_none()
            serialized = json.dumps(value, default=str)

            if row:
                row.value = serialized
            else:
                session.add(AnalyticsCache(key=key, value=serialized))

        await session.commit()

    return {
        "status": "ok",
        "cached_keys": ["summary", "top_products", "categories"],
        "summary_total_orders": summary["total_orders"],
    }


@celery_app.task(name="analytics.recompute")
def recompute_analytics():
    """
    Celery task: recompute all cached analytics.
    
    In production this runs in a background worker.
    Locally it runs synchronously due to task_always_eager=True.
    """
    print("🔄 Running analytics recomputation task...")
    result = asyncio.run(_recompute_summary_async())
    print(f"✅ Cached: {result['cached_keys']}")
    return result