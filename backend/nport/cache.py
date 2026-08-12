import asyncio
import time
from collections import OrderedDict
from typing import Awaitable, Callable, Generic, Hashable, TypeVar

T = TypeVar("T")

FILING_TTL = 3600.0
MAX_ENTRIES = 32

# Async-safe TTL + LRU cache with single-flight semantics
class TTLCache(Generic[T]):
    def __init__(self, ttl: float = FILING_TTL, maxsize: int = MAX_ENTRIES):
        self._ttl = ttl
        self._maxsize = maxsize
        self._entries: OrderedDict[Hashable, tuple[float, T]] = OrderedDict()
        self._locks: dict[Hashable, tuple[asyncio.Lock, int]] = {}
        self._guard = asyncio.Lock()

    def _get_fresh(self, key: Hashable) -> T | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return value

    def get(self, key: Hashable) -> T | None:
        return self._get_fresh(key)

    def set(self, key: Hashable, value: T) -> None:
        self._entries[key] = (time.monotonic() + self._ttl, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._maxsize:
            self._entries.popitem(last=False)

    # Return a cached value or await the loader
    async def get_or_load(self, key: Hashable, loader: Callable[[], Awaitable[T]]) -> T:
        cached = self._get_fresh(key)
        if cached is not None:
            return cached

        async with self._guard:
            lock, waiters = self._locks.get(key, (asyncio.Lock(), 0))
            self._locks[key] = (lock, waiters + 1)

        try:
            async with lock:
                # A concurrent caller may have populated the entry while we waited on the lock
                cached = self._get_fresh(key)
                if cached is not None:
                    return cached
                value = await loader()
                self.set(key, value)
                return value
        finally:
            async with self._guard:
                _, remaining = self._locks[key]
                if remaining <= 1:
                    self._locks.pop(key, None)
                else:
                    self._locks[key] = (lock, remaining - 1)

    def clear(self) -> None:
        self._entries.clear()

    @property
    def size(self) -> int:
        return len(self._entries)
