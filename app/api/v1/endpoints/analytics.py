"""
Analytics endpoints — business intelligence over the e-commerce data.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.core.database import get_db
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.analytics import (
    SummaryResponse,
    TopProductItem,
    RevenueTrendItem,
    CategoryPerformanceItem,
)


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(db: AsyncSession = Depends(get_db)):
    """Get top-level business KPIs."""
    return await AnalyticsRepository.get_summary(db)


@router.get("/top-products", response_model=List[TopProductItem])
async def get_top_products(
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get best-selling products by revenue."""
    return await AnalyticsRepository.get_top_products(db, limit)


@router.get("/revenue-trends", response_model=List[RevenueTrendItem])
async def get_revenue_trends(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get daily revenue for the last N days."""
    return await AnalyticsRepository.get_revenue_trends(db, days)


@router.get("/category-performance", response_model=List[CategoryPerformanceItem])
async def get_category_performance(db: AsyncSession = Depends(get_db)):
    """Get revenue and items sold by product category."""
    return await AnalyticsRepository.get_category_performance(db)