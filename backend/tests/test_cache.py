import asyncio

import pytest

from nport.cache import TTLCache

async def test_returns_cached_value():
    cache: TTLCache[str] = TTLCache(ttl=60)
    calls = {"n": 0}

    async def loader() -> str:
        calls["n"] += 1
        return "value"

    assert await cache.get_or_load("k", loader) == "value"
    assert await cache.get_or_load("k", loader) == "value"
    assert calls["n"] == 1

async def test_expired_entry_reloads():
    cache: TTLCache[str] = TTLCache(ttl=0.01)
    calls = {"n": 0}

    async def loader() -> str:
        calls["n"] += 1
        return f"v{calls['n']}"

    await cache.get_or_load("k", loader)
    await asyncio.sleep(0.02)
    assert await cache.get_or_load("k", loader) == "v2"

# Cached filings are large, so the cache must stay bounded
async def test_evicts_least_recently_used():
    cache: TTLCache[str] = TTLCache(ttl=60, maxsize=2)

    async def loader(value: str):
        async def _inner() -> str:
            return value
        return _inner

    await cache.get_or_load("a", await loader("a"))
    await cache.get_or_load("b", await loader("b"))
    await cache.get_or_load("a", await loader("a"))
    await cache.get_or_load("c", await loader("c"))

    assert cache.size == 2
    assert cache.get("b") is None, "least recently used should be removed"
    assert cache.get("a") == "a"

async def test_concurrent_misses_load_once():
    cache: TTLCache[str] = TTLCache(ttl=60)
    calls = {"n": 0}

    async def loader() -> str:
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return "value"

    results = await asyncio.gather(
        *(cache.get_or_load("k", loader) for _ in range(5))
    )
    assert results == ["value"] * 5
    assert calls["n"] == 1

async def test_failed_load_is_not_cached():
    cache: TTLCache[str] = TTLCache(ttl=60)

    async def failing() -> str:
        raise RuntimeError("upstream down")

    with pytest.raises(RuntimeError):
        await cache.get_or_load("k", failing)
    assert cache.get("k") is None
    assert cache.size == 0
