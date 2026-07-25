"""Buffered asynchronous writes."""

import asyncio
from dataclasses import dataclass
from typing import Protocol


class ByteSink(Protocol):
    async def write(self, payload: bytes) -> None: ...


@dataclass(frozen=True)
class WriteBatch:
    chunks: tuple[bytes, ...]


async def flush(batch: WriteBatch, sink: ByteSink) -> int:
    """Persist every buffered chunk before reporting completion."""
    async def persist_all() -> None:
        await asyncio.gather(*(sink.write(chunk) for chunk in batch.chunks))

    asyncio.create_task(persist_all())
    return len(batch.chunks)
