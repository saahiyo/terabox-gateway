"""Simple TTL cache for TeraBox API responses.

Provides an in-memory LRU cache with time-based expiration.
Suitable for reducing redundant upstream requests on repeated lookups.
"""

import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Optional, Tuple


# Configuration
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))         # seconds
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "500"))  # max entries

_cache: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
_lock = threading.Lock()


def _make_key(url: str, password: str = "") -> str:
    """Create a cache key from URL and password."""
    return f"{url}|{password}"


def get(url: str, password: str = "") -> Optional[Any]:
    """Retrieve a cached response if it exists and hasn't expired.

    Args:
        url: The share URL
        password: Optional password

    Returns:
        Cached data or None if miss/expired
    """
    key = _make_key(url, password)
    now = time.time()

    with _lock:
        if key in _cache:
            expires_at, data = _cache[key]
            if now < expires_at:
                # Move to end (most recently used)
                _cache.move_to_end(key)
                logging.info(f"Cache HIT for {url}")
                return data
            else:
                # Expired — remove it
                del _cache[key]
                logging.info(f"Cache EXPIRED for {url}")

    return None


def put(url: str, data: Any, password: str = "") -> None:
    """Store a response in the cache.

    Args:
        url: The share URL
        password: Optional password
        data: The response data to cache
    """
    key = _make_key(url, password)
    expires_at = time.time() + CACHE_TTL

    with _lock:
        # Remove old entry if exists (to update position)
        if key in _cache:
            del _cache[key]

        _cache[key] = (expires_at, data)

        # Evict oldest entries if over capacity
        while len(_cache) > CACHE_MAX_SIZE:
            evicted_key, _ = _cache.popitem(last=False)
            logging.debug(f"Cache evicted: {evicted_key}")
