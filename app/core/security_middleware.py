"""Security middleware and utilities.

- Rate limiting
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- Audit logging
- 152-FZ personal data compliance helpers
- Request sanitization
"""

import time
from typing import Callable, Dict, Optional
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Rate Limiting ────────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter per IP."""

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Skip rate limiting for health checks and static files
        if path in ("/health", "/", "/docs", "/redoc") or path.startswith("/static"):
            return await call_next(request)

        now = time.time()
        key = f"{client_ip}:{path}"

        if key not in self._requests:
            self._requests[key] = []

        # Clean old entries
        self._requests[key] = [t for t in self._requests[key] if now - t < self.window_seconds]

        if len(self._requests[key]) >= self.max_requests:
            logger.warning("rate_limit_exceeded", extra={"extra": {"ip": client_ip, "path": path}})
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Try again later."},
            )

        self._requests[key].append(now)
        return await call_next(request)


# ── Security Headers ─────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security-related headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS (only in production with HTTPS)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # CSP for API responses
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        return response


# ── Audit Logging ────────────────────────────────────────────────────

class AuditLogMiddleware(BaseHTTPMiddleware):
    """Log all mutating requests for audit trail (152-FZ compliance)."""

    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if request.method in self.MUTATING_METHODS:
            client_ip = request.client.host if request.client else "unknown"
            path = request.url.path

            # Extract user info if available
            auth_header = request.headers.get("authorization", "")
            user_id = "anonymous"
            if auth_header.startswith("Bearer "):
                try:
                    from app.core.security import decode_access_token
                    payload = decode_access_token(auth_header[7:])
                    if payload:
                        user_id = payload.get("sub", "unknown")
                except Exception:
                    pass

            logger.info("audit_log", extra={
                "extra": {
                    "method": request.method,
                    "path": path,
                    "status_code": response.status_code,
                    "client_ip": client_ip,
                    "user_id": user_id,
                }
            })

        return response


# ── Personal Data (152-FZ) Helpers ───────────────────────────────────

class PersonalDataHandler:
    """Helpers for 152-FZ (Russian Personal Data Law) compliance."""

    @staticmethod
    def mask_phone(phone: str) -> str:
        """Mask phone number for logging: +7(999)***-**-99"""
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) >= 10:
            return f"+{digits[0]}({digits[1:4]})***-**-{digits[-2:]}"
        return "***"

    @staticmethod
    def mask_email(email: str) -> str:
        """Mask email for logging: u***@domain.com"""
        if "@" in email:
            local, domain = email.split("@", 1)
            if len(local) > 1:
                return f"{local[0]}***@{domain}"
        return "***@***"

    @staticmethod
    def mask_inn(inn: str) -> str:
        """Mask INN for logging: 7707******3"""
        if len(inn) >= 4:
            return f"{inn[:4]}******{inn[-1]}"
        return "***"

    @staticmethod
    def consent_required_fields() -> list:
        """Fields that require explicit user consent under 152-FZ."""
        return [
            "full_name", "phone", "email", "address",
            "passport_data", "inn", "vehicle_vin", "license_plate",
        ]

    @staticmethod
    def data_retention_policy() -> dict:
        """Data retention periods per 152-FZ."""
        return {
            "order_data": "3 years after order completion",
            "personal_data": "until consent withdrawal + 1 year",
            "financial_data": "5 years (tax regulations)",
            "audit_logs": "3 years",
            "anonymized_data": "indefinitely",
        }
