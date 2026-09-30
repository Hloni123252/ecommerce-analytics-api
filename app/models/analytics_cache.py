from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.core.database import Base


class AnalyticsCache(Base):
    """Simple key-value cache for precomputed analytics."""
    __tablename__ = "analytics_cache"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)  # JSON string
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())