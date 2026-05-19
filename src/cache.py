"""
Disk-based result cache.
Keyed by (video_id, query_normalized) to avoid redundant LLM calls.
"""

import hashlib
import os
from typing import Optional

import diskcache

_CACHE_DIR = os.getenv("CACHE_DIR", ".result_cache")
_TTL = int(os.getenv("CACHE_TTL_SECONDS", "86400"))  # 24h default

_cache: Optional[diskcache.Cache] = None


def _get_cache() -> diskcache.Cache:
    global _cache
    if _cache is None:
        _cache = diskcache.Cache(_CACHE_DIR)
    return _cache


def _make_key(video_id: str, query: str) -> str:
    normalized = query.lower().strip()
    raw = f"{video_id}::{normalized}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get(video_id: str, query: str) -> Optional[dict]:
    key = _make_key(video_id, query)
    return _get_cache().get(key)


def set(video_id: str, query: str, result: dict) -> None:
    key = _make_key(video_id, query)
    _get_cache().set(key, result, expire=_TTL)


def invalidate(video_id: str, query: str) -> None:
    key = _make_key(video_id, query)
    _get_cache().delete(key)


def stats() -> dict:
    c = _get_cache()
    return {"size": len(c), "volume_bytes": c.volume()}
