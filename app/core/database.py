from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings


engine_kwargs = {
    "echo": False,
    "future": True,
    # Handle stale connections gracefully (important for Neon/Render)
    "pool_pre_ping": True,
    "pool_recycle": 300,
    # Small pool for free tier
    "pool_size": 5,
    "max_overflow": 5,
}

db_url = settings.database_url

if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine_kwargs.pop("pool_size", None)
    engine_kwargs.pop("max_overflow", None)

engine = create_async_engine(db_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session