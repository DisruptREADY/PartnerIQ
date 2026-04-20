"""Simple in-memory TTL cache for API responses with thread safety and LRU eviction."""
import hashlib
import json
import threading
import time
from typing import Any, Dict, Optional

CACHE_TTL = 900  # 15 minutes
MAX_ENTRIES = 200  # Maximum cache entries before LRU eviction

_cache: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def _make_key(cbsas: list, indicators: list, years: list, geo_type: str = "msa", acs_dataset: str = "acs1") -> str:
    """Hash request params into a cache key."""
    payload = json.dumps({
        "cbsas": sorted(cbsas),
        "indicators": sorted(indicators),
        "years": sorted(years),
        "geo_type": geo_type,
        "acs_dataset": acs_dataset,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _purge_expired_locked():
    """Remove expired entries while holding the lock."""
    now = time.time()
    expired = [k for k, v in _cache.items() if now - v["timestamp"] > CACHE_TTL]
    for k in expired:
        del _cache[k]


def _evict_lru_locked():
    """Evict least-recently-accessed entries if over MAX_ENTRIES."""
    if len(_cache) <= MAX_ENTRIES:
        return
    # Sort by last_access ascending, evict oldest
    by_access = sorted(_cache.items(), key=lambda kv: kv[1].get("last_access", kv[1]["timestamp"]))
    to_remove = len(_cache) - MAX_ENTRIES
    for key, _ in by_access[:to_remove]:
        del _cache[key]


def get_cached(cbsas: list, indicators: list, years: list, geo_type: str = "msa", acs_dataset: str = "acs1") -> Optional[Dict[str, Any]]:
    """Return cached response if available and not expired."""
    key = _make_key(cbsas, indicators, years, geo_type, acs_dataset)
    with _lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > CACHE_TTL:
            del _cache[key]
            return None
        entry["last_access"] = time.time()
        return entry["data"]


def set_cached(cbsas: list, indicators: list, years: list, data: Dict[str, Any], geo_type: str = "msa", acs_dataset: str = "acs1"):
    """Store a response in the cache."""
    key = _make_key(cbsas, indicators, years, geo_type, acs_dataset)
    now = time.time()
    with _lock:
        _cache[key] = {"data": data, "timestamp": now, "last_access": now}
        _purge_expired_locked()
        _evict_lru_locked()


def clear_cache():
    """Clear all cached entries."""
    with _lock:
        _cache.clear()


def cache_stats() -> Dict[str, Any]:
    """Return cache statistics."""
    with _lock:
        now = time.time()
        active = sum(1 for e in _cache.values() if now - e["timestamp"] <= CACHE_TTL)
        return {"entries": len(_cache), "active": active, "ttl_seconds": CACHE_TTL, "max_entries": MAX_ENTRIES}
