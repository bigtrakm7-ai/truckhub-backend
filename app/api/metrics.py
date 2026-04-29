"""Prometheus metrics for monitoring.

Exposes metrics at /metrics endpoint for Prometheus scraping.
"""

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import APIRouter, Response
from functools import wraps
import time

router = APIRouter()

# ── Metrics Definitions ─────────────────────────────────────────────

# Request metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Business metrics
ORDERS_CREATED = Counter(
    "orders_created_total",
    "Total orders created",
    ["status"]
)

USERS_REGISTERED = Counter(
    "users_registered_total",
    "Total user registrations",
    ["role"]
)

# System metrics
ACTIVE_CONNECTIONS = Gauge(
    "active_connections",
    "Number of active connections"
)

CACHE_HITS = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_type"]
)

CACHE_MISSES = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_type"]
)

# Application info
APP_INFO = Info("app_info", "Application information")


# ── Middleware ──────────────────────────────────────────────────────

class PrometheusMiddleware:
    """FastAPI middleware to track request metrics."""
    
    def __init__(self, app):
        self.app = app
        APP_INFO.info({"version": "1.0.0", "name": "truckhub"})
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        
        # Skip metrics endpoint itself
        if path == "/metrics":
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        
        # Capture status code
        status_code = 200
        
        async def wrapped_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await send(message)
        
        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            duration = time.time() - start_time
            
            # Record metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status_code=str(status_code)
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=path
            ).observe(duration)


# ── Decorators ──────────────────────────────────────────────────────

def track_duration(name: str):
    """Decorator to track function execution time."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.time() - start
                REQUEST_DURATION.labels(
                    method="FUNCTION",
                    endpoint=name
                ).observe(duration)
        return wrapper
    return decorator


def track_business_event(event_type: str, labels: dict = None):
    """Track business events (orders, registrations, etc.)."""
    if event_type == "order_created":
        ORDERS_CREATED.labels(status=labels.get("status", "unknown")).inc()
    elif event_type == "user_registered":
        USERS_REGISTERED.labels(role=labels.get("role", "unknown")).inc()


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@router.get("/health/detailed")
async def detailed_health():
    """Detailed health check with component status."""
    from app.core.database import get_redis, get_elasticsearch
    
    checks = {
        "database": "unknown",
        "redis": "unknown",
        "elasticsearch": "unknown",
    }
    
    # Check Redis
    try:
        redis = await get_redis()
        if redis and await redis.ping():
            checks["redis"] = "healthy"
        else:
            checks["redis"] = "unavailable"
    except Exception:
        checks["redis"] = "error"
    
    # Check Elasticsearch
    try:
        es = await get_elasticsearch()
        if es and await es.ping():
            checks["elasticsearch"] = "healthy"
        else:
            checks["elasticsearch"] = "unavailable"
    except Exception:
        checks["elasticsearch"] = "error"
    
    # Overall status
    all_healthy = all(v == "healthy" for v in checks.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": time.time(),
        "checks": checks,
    }
