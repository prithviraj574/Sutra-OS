from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Generic, TypeVar


TEvent = TypeVar("TEvent")
TResult = TypeVar("TResult")


class AsyncEventStream(Generic[TEvent, TResult]):
    def __init__(self) -> None:
        self._queue: asyncio.Queue[TEvent | None] = asyncio.Queue()
        self._done = asyncio.Event()
        self._result: TResult | None = None

    def push(self, event: TEvent) -> None:
        self._queue.put_nowait(event)

    def end(self, result: TResult) -> None:
        self._result = result
        self._done.set()
        self._queue.put_nowait(None)

    def __aiter__(self) -> AsyncIterator[TEvent]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[TEvent]:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            yield item

    async def result(self) -> TResult:
        await self._done.wait()
        return self._result  # type: ignore[return-value]
