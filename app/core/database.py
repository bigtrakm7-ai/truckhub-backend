from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Database Engine ──────────────────────────────────────────────────

_database_url = settings.DATABASE_URL

# Auto-detect and adapt for PostgreSQL
if _database_url.startswith("postgresql://"):
    _database_url = _database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    logger.info("database_postgresql_detected")
elif _database_url.startswith("postgres://"):
    _database_url = _database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    logger.info("database_postgres_detected")

engine_kwargs = {
    "echo": settings.ENV == "dev",
    "pool_pre_ping": True,
}

if _database_url.startswith("postgresql"):
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_recycle": 300,
        "pool_timeout": 30,
    })
    logger.info("database_pool_configured", extra={"extra": {"pool_size": 20}})
else:
    # SQLite-specific settings
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(_database_url, **engine_kwargs)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


# ── Redis ────────────────────────────────────────────────────────────

_redis_client = None


async def get_redis():
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
            )
            await _redis_client.ping()
            logger.info("redis_connected", extra={"extra": {"url": settings.REDIS_URL}})
        except Exception as exc:
            logger.warning("redis_unavailable", extra={"extra": {"error": str(exc)}})
            _redis_client = None
    return _redis_client


async def get_redis_client():
    """FastAPI dependency for Redis."""
    client = await get_redis()
    if client is None:
        raise Exception("Redis is not available")
    return client


async def close_redis():
    """Close Redis connection on shutdown."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("redis_disconnected")


# ── Elasticsearch ────────────────────────────────────────────────────

_es_client = None


async def get_elasticsearch():
    """Get or create Elasticsearch client."""
    global _es_client
    if _es_client is None:
        try:
            from elasticsearch import AsyncElasticsearch
            _es_client = AsyncElasticsearch(
                hosts=[settings.ELASTICSEARCH_URL],
                timeout=15,
                max_retries=3,
                retry_on_timeout=True,
            )
            health = await _es_client.ping()
            if health:
                logger.info("elasticsearch_connected", extra={"extra": {"url": settings.ELASTICSEARCH_URL}})
            else:
                logger.warning("elasticsearch_ping_failed")
                _es_client = None
        except Exception as exc:
            logger.warning("elasticsearch_unavailable", extra={"extra": {"error": str(exc)}})
            _es_client = None
    return _es_client


async def close_elasticsearch():
    """Close Elasticsearch connection on shutdown."""
    global _es_client
    if _es_client:
        await _es_client.close()
        _es_client = None
        logger.info("elasticsearch_disconnected")


# ── Startup / Shutdown ──────────────────────────────────────────────

async def init_db():
    """Initialize database, create tables if needed."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_initialized")


async def close_db():
    """Close all connections."""
    await engine.dispose()
    await close_redis()
    await close_elasticsearch()
    logger.info("database_connections_closed")
