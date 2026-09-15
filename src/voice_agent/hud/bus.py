"""Asyncio EventBus — decouples agent stages from TUI subscribers."""
from __future__ import annotations
import asyncio
from typing import Any


_SENTINEL: Any = object()


class Subscription:
    """Async iterator over events from a single subscription."""

    def __init__(self, queue: asyncio.Queue) -> None:
        self._q = queue

    async def next(self) -> Any:
        ev = await self._q.get()
        if ev is _SENTINEL:
            raise StopAsyncIteration
        return ev

    def __aiter__(self) -> "Subscription":
        return self

    async def __anext__(self) -> Any:
        ev = await self._q.get()
        if ev is _SENTINEL:
            raise StopAsyncIteration
        return ev


class EventBus:
    """Multi-subscriber asyncio event bus. Each subscriber gets its own queue."""

    def __init__(self, maxsize: int = 1024) -> None:
        self._subscribers: list[asyncio.Queue] = []
        self._maxsize = maxsize
        self._closed = False

    def subscribe(self) -> Subscription:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.append(q)
        return Subscription(q)

    def publish(self, event: Any) -> None:
        if self._closed:
            return
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # drop on slow subscriber; non-fatal
                pass

    async def close(self) -> None:
        self._closed = True
        for q in list(self._subscribers):
            await q.put(_SENTINEL)
        self._subscribers.clear()
