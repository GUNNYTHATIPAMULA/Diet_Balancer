"""Adds an X-Request-ID header to every response and logs request timing."""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("diet_balancer.requests")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info("%s %s -> %s (%.1f ms) [%s]", request.method, request.url.path,
                    response.status_code, elapsed_ms, request_id)
        return response
