"""Small in-memory sliding-window rate limiter.

Good enough for a single-process deployment. If you run several API workers,
move this to Redis or enforce limits at the reverse proxy instead."""
import threading
import time
from collections import defaultdict, deque

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import RateLimitedError

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def reset_rate_limits() -> None:
    with _lock:
        _hits.clear()


def rate_limit(name: str, limit: int, window_seconds: int):
    def dependency(request: Request) -> None:
        if not get_settings().RATE_LIMIT_ENABLED:
            return
        client = request.client.host if request.client else "unknown"
        key = f"{name}:{client}"
        now = time.monotonic()
        with _lock:
            bucket = _hits[key]
            while bucket and now - bucket[0] > window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                retry = int(window_seconds - (now - bucket[0])) + 1
                raise RateLimitedError(
                    f"Too many requests. Try again in {retry} seconds.", details={"retry_after_seconds": retry}
                )
            bucket.append(now)

    return dependency
