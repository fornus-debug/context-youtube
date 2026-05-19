import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    # Force re-import to pick up new env var
    import src.cache as c
    c._cache = None
    yield
    if c._cache:
        c._cache.close()
    c._cache = None


def test_cache_miss_returns_none():
    from src.cache import get
    assert get("vid123", "what is this?") is None


def test_cache_set_and_get():
    from src.cache import get, set
    result = {"answer": "Test answer", "cost": {"total_jpy": 0.5}}
    set("vid123", "what is this?", result)
    cached = get("vid123", "what is this?")
    assert cached is not None
    assert cached["answer"] == "Test answer"


def test_cache_key_normalized():
    from src.cache import get, set
    result = {"answer": "normalized"}
    set("vid", "  Hello World  ", result)
    # Same query with different casing/spacing should NOT match (we only normalize case+strip)
    assert get("vid", "hello world") is not None


def test_cache_invalidate():
    from src.cache import get, invalidate, set
    set("vid", "query", {"answer": "x"})
    invalidate("vid", "query")
    assert get("vid", "query") is None
