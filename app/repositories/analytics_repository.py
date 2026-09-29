"""
Repository for analytics queries — aggregations, trends, rankings.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models import Customer, Product, Order, OrderItem


class AnalyticsRepository:
    @staticmethod
    async def get_summary(db: AsyncSession) -> dict:
        """High-level business KPIs."""
        # Revenue + orders
        orders_result = await db.execute(
            select(
                func.count(Order.id).label("total_orders"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_revenue"),
            )
        )
        row = orders_result.one()
        total_orders = row.total_orders or 0
        total_revenue = float(row.total_revenue or 0)

        # Customers
        customers_result = await db.execute(
            select(func.count(Customer.id))
        )
        total_customers = customers_result.scalar() or 0

        # Products
        products_result = await db.execute(
            select(func.count(Product.id))
        )
        total_products = products_result.scalar() or 0

        # Average order value
        aov = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

        return {
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "total_customers": total_customers,
            "total_products": total_products,
            "average_order_value": aov,
        }

    @staticmethod
    async def get_top_products(db: AsyncSession, limit: int = 10) -> list[dict]:
        """Best-selling products by revenue."""
        revenue_expr = func.sum(OrderItem.quantity * OrderItem.unit_price)

        result = await db.execute(
            select(
                Product.id.label("product_id"),
                Product.name.label("product_name"),
                Product.category.label("category"),
                func.sum(OrderItem.quantity).label("total_quantity"),
                revenue_expr.label("total_revenue"),
                func.count(func.distinct(OrderItem.order_id)).label("order_count"),
            )
            .join(OrderItem, Product.id == OrderItem.product_id)
            .group_by(Product.id, Product.name, Product.category)
            .order_by(desc(revenue_expr))
            .limit(limit)
        )

        return [
            {
                "product_id": r.product_id,
                "product_name": r.product_name,
                "category": r.category,
                "total_quantity": int(r.total_quantity or 0),
                "total_revenue": round(float(r.total_revenue or 0), 2),
                "order_count": int(r.order_count or 0),
            }
            for r in result.all()
        ]

    @staticmethod
    async def get_revenue_trends(db: AsyncSession, days: int = 30) -> list[dict]:
        """
        Daily revenue for the last N days.
        
        Uses SQL date() function — works in both SQLite and Postgres.
        """
        date_expr = func.date(Order.created_at)

        result = await db.execute(
            select(
                date_expr.label("date"),
                func.count(Order.id).label("order_count"),
                func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
            )
            .group_by(date_expr)
            .order_by(desc(date_expr))
            .limit(days)
        )

        return [
            {
                "date": r.date,
                "order_count": int(r.order_count or 0),
                "revenue": round(float(r.revenue or 0), 2),
            }
            for r in result.all()
        ]

    @staticmethod
    async def get_category_performance(db: AsyncSession) -> list[dict]:
        """Revenue and items sold per product category."""
        revenue_expr = func.sum(OrderItem.quantity * OrderItem.unit_price)

        result = await db.execute(
            select(
                Product.category.label("category"),
                func.sum(OrderItem.quantity).label("items_sold"),
                revenue_expr.label("revenue"),
                func.count(func.distinct(Product.id)).label("product_count"),
            )
            .join(OrderItem, Product.id == OrderItem.product_id)
            .group_by(Product.category)
            .order_by(desc(revenue_expr))
        )

        return [
            {
                "category": r.category,
                "items_sold": int(r.items_sold or 0),
                "revenue": round(float(r.revenue or 0), 2),
                "product_count": int(r.product_count or 0),
            }
            for r in result.all()
        ]