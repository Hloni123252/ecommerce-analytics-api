"""
Pydantic schemas for analytics responses.
"""
from pydantic import BaseModel
from typing import List
from decimal import Decimal
from datetime import date


class SummaryResponse(BaseModel):
    total_revenue: Decimal
    total_orders: int
    total_customers: int
    total_products: int
    average_order_value: Decimal


class TopProductItem(BaseModel):
    product_id: int
    product_name: str
    category: str
    total_quantity: int
    total_revenue: Decimal
    order_count: int


class RevenueTrendItem(BaseModel):
    date: date
    order_count: int
    revenue: Decimal


class CategoryPerformanceItem(BaseModel):
    category: str
    items_sold: int
    revenue: Decimal
    product_count: int