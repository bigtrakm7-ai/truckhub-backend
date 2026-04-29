"""Performance optimization layer — caching, query optimization, lazy loading.

Targets:
- Page load: < 2 seconds
- Search: < 0.5 seconds
"""

import json
import hashlib
from typing import Any, Optional, Callable
from functools import wraps
from datetime import datetime, timedelta
from app.core.logging import get_logger
from app.core.database import get_redis

logger = get_logger(__name__)

# ── Cache Decorators ────────────────────────────────────────────────

def cache_response(ttl_seconds: int = 60, key_prefix: str = "api"):
    """Decorator to cache API responses in Redis."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            cache_key = f"{key_prefix}:{func.__name__}:{_hash_args(args, kwargs)}"
            
            # Try to get from cache
            try:
                redis = await get_redis()
                if redis:
                    cached = await redis.get(cache_key)
                    if cached:
                        logger.debug("cache_hit", extra={"extra": {"key": cache_key}})
                        return json.loads(cached)
            except Exception as exc:
                logger.warning("cache_read_error", extra={"extra": {"error": str(exc)}})
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            try:
                redis = await get_redis()
                if redis and result is not None:
                    await redis.setex(
                        cache_key,
                        ttl_seconds,
                        json.dumps(result, default=_json_serializer)
                    )
                    logger.debug("cache_set", extra={"extra": {"key": cache_key, "ttl": ttl_seconds}})
            except Exception as exc:
                logger.warning("cache_write_error", extra={"extra": {"error": str(exc)}})
            
            return result
        return wrapper
    return decorator


def invalidate_cache(pattern: str):
    """Invalidate cache keys matching pattern."""
    async def _invalidate():
        try:
            redis = await get_redis()
            if redis:
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
                    logger.info("cache_invalidate", extra={"extra": {"pattern": pattern, "keys": len(keys)}})
        except Exception as exc:
            logger.warning("cache_invalidate_error", extra={"extra": {"error": str(exc)}})
    return _invalidate


# ── Query Optimization ─────────────────────────────────────────────

class QueryOptimizer:
    """SQL query optimization helpers."""
    
    @staticmethod
    def optimize_catalog_query(query, filters: dict):
        """Apply query optimizations for catalog search."""
        # Use selectinload for relationships to avoid N+1
        from sqlalchemy.orm import selectinload
        from app.models.product import Product
        
        query = query.options(
            selectinload(Product.category),
            selectinload(Product.brand),
        )
        
        # Add covering index hints for common filters
        if filters.get("in_stock"):
            query = query.filter(Product.stock_quantity > 0)
        
        if filters.get("is_premium"):
            query = query.filter(Product.is_premium == True)
        
        return query
    
    @staticmethod
    def optimize_order_query(query):
        """Optimize order queries with proper joins."""
        from sqlalchemy.orm import selectinload
        from app.models.order import Order
        
        return query.options(
            selectinload(Order.items),
            selectinload(Order.shipments),
        )


# ── Lazy Loading Helpers ───────────────────────────────────────────

class LazyLoader:
    """Helpers for lazy loading heavy content."""
    
    @staticmethod
    def paginate(query, page: int = 1, per_page: int = 20):
        """Apply pagination with optimized offset/limit."""
        # Use keyset pagination for large offsets
        if page > 100:
            # Fallback to offset for simplicity, but log warning
            logger.warning("large_offset_query", extra={"extra": {"page": page}})
        
        offset = (page - 1) * per_page
        return query.offset(offset).limit(per_page)
    
    @staticmethod
    async def load_images_lazy(product_ids: list, db) -> dict:
        """Load product images only when needed."""
        # Placeholder for S3 image URLs
        return {pid: [] for pid in product_ids}


# ── Search Optimization ────────────────────────────────────────────

class SearchOptimizer:
    """Optimize catalog search for <0.5s response."""
    
    # Common search terms cache
    _popular_searches: dict = {}
    _last_updated: Optional[datetime] = None
    
    @classmethod
    async def get_popular_searches(cls, limit: int = 10) -> list:
        """Get cached popular searches."""
        if cls._last_updated and datetime.utcnow() - cls._last_updated < timedelta(minutes=5):
            return list(cls._popular_searches.keys())[:limit]
        
        # Refresh from DB or analytics
        # For now, return static popular terms
        popular = ["KAMAZ", "Mercedes", "тормозные колодки", "фильтр", "ремень"]
        cls._popular_searches = {k: True for k in popular}
        cls._last_updated = datetime.utcnow()
        return popular[:limit]
    
    @classmethod
    def optimize_search_query(cls, query_text: str) -> str:
        """Normalize and optimize search query."""
        # Remove extra spaces
        query_text = " ".join(query_text.split())
        
        # Convert to lowercase for case-insensitive search
        query_text = query_text.lower()
        
        # Expand common abbreviations
        expansions = {
            "камаз": "KAMAZ",
            "маз": "MAZ",
            "газ": "GAZ",
        }
        
        for short, full in expansions.items():
            if short in query_text:
                query_text = f"{query_text} {full}"
        
        return query_text.strip()


# ── Helpers ────────────────────────────────────────────────────────

def _hash_args(args: tuple, kwargs: dict) -> str:
    """Create hash from function arguments for cache key."""
    key_data = f"{args}:{sorted(kwargs.items())}"
    return hashlib.md5(key_data.encode()).hexdigest()[:16]


def _json_serializer(obj):
    """JSON serializer for datetime and other non-serializable types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


# ── Performance Monitoring ─────────────────────────────────────────

class PerformanceMonitor:
    """Track and log performance metrics."""
    
    @staticmethod
    def measure(func: Callable) -> Callable:
        """Decorator to measure function execution time."""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import time
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.time() - start
                if elapsed > 0.5:  # Log slow queries
                    logger.warning("slow_query", extra={
                        "extra": {
                            "function": func.__name__,
                            "elapsed_ms": round(elapsed * 1000, 2),
                        }
                    })
        return wrapper
