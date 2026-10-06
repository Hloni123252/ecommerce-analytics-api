"""
Admin endpoints: trigger background tasks, inspect cache.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.core.database import get_db
from app.models.analytics_cache import AnalyticsCache
from app.tasks.analytics_tasks import recompute_analytics


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/recompute")
def trigger_recompute():
    """Trigger a background recomputation of analytics cache."""
    task = recompute_analytics.delay()
    return {"task_id": task.id, "status": "queued"}


@router.get("/cache")
async def list_cache(db: AsyncSession = Depends(get_db)):
    """List all cached analytics entries."""
    result = await db.execute(
        select(AnalyticsCache).order_by(AnalyticsCache.key)
    )
    rows = result.scalars().all()

    return [
        {
            "key": row.key,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "preview": json.loads(row.value) if row.key == "summary" else "[cached]",
        }
        for row in rows
    ]