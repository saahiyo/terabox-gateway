"""In-memory sliding-window rate limiter.

Provides a lightweight per-IP rate limiter that requires zero external
dependencies. Suitable for single-instance deployments (Vercel serverless).
"""

import os
import time
import threading
from collections import defaultdict
from functools import wraps
from flask import request, jsonify


# Configuration via environment variables
MAX_REQUESTS = int(os.getenv("RATE_LIMIT", "30"))  # requests per window
WINDOW_SECONDS = int(os.getenv("RATE_WINDOW", "60"))  # window size in seconds

# Thread-safe storage: {ip: [timestamp, ...]}
_hits: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()


def _get_client_ip() -> str:
    """Get the real client IP, respecting reverse-proxy headers."""
    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.headers.get("X-Real-IP")
        or request.remote_addr
        or "unknown"
    )


def _cleanup_old_entries(ip: str, now: float) -> None:
    """Remove timestamps older than the current window."""
    cutoff = now - WINDOW_SECONDS
    _hits[ip] = [t for t in _hits[ip] if t > cutoff]


def rate_limit(f):
    """Decorator that enforces per-IP rate limiting on a Flask route.

    Returns 429 Too Many Requests with a Retry-After header when the
    client exceeds MAX_REQUESTS within WINDOW_SECONDS.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        ip = _get_client_ip()
        now = time.time()

        with _lock:
            _cleanup_old_entries(ip, now)
            if len(_hits[ip]) >= MAX_REQUESTS:
                # Calculate when the oldest request in the window expires
                retry_after = int(WINDOW_SECONDS - (now - _hits[ip][0])) + 1
                return jsonify({
                    "status": "error",
                    "message": "Rate limit exceeded",
                    "retry_after": retry_after,
                    "limit": f"{MAX_REQUESTS} requests per {WINDOW_SECONDS}s",
                }), 429, {"Retry-After": str(retry_after)}

            _hits[ip].append(now)

        return f(*args, **kwargs)

    # Support async route handlers (Flask 3.x)
    if __import__("asyncio").iscoroutinefunction(f):
        @wraps(f)
        async def async_wrapper(*args, **kwargs):
            ip = _get_client_ip()
            now = time.time()

            with _lock:
                _cleanup_old_entries(ip, now)
                if len(_hits[ip]) >= MAX_REQUESTS:
                    retry_after = int(WINDOW_SECONDS - (now - _hits[ip][0])) + 1
                    return jsonify({
                        "status": "error",
                        "message": "Rate limit exceeded",
                        "retry_after": retry_after,
                        "limit": f"{MAX_REQUESTS} requests per {WINDOW_SECONDS}s",
                    }), 429, {"Retry-After": str(retry_after)}

                _hits[ip].append(now)

            return await f(*args, **kwargs)
        return async_wrapper

    return wrapper
