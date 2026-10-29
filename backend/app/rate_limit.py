"""Very small in-process sliding-window rate limiter.

Keeps a demo deployment from being hammered without adding Redis or any other
dependency. Limits are per client IP and reset automatically.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= now - self.window_seconds:
                bucket.popleft()
            if len(bucket) >= self.max_requests:
                retry_in = int(self.window_seconds - (now - bucket[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": "rate_limited",
                        "message": f"Too many requests. Try again in {retry_in}s.",
                        "retry_after": retry_in,
                    },
                    headers={"Retry-After": str(retry_in)},
                )
            bucket.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def rate_limit(request: Request, limiter: SlidingWindowLimiter) -> None:
    limiter.check(client_key(request))
