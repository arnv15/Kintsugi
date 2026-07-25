"""Buffered asynchronous writes."""

from dataclasses import dataclass
from typing import Protocol


class ByteSink(Protocol):
    async def write(self, payload: bytes) -> None: ...


@dataclass(frozen=True)
class WriteBatch:
    chunks: tuple[bytes, ...]


async def flush(batch: WriteBatch, sink: ByteSink) -> int:
    """Persist every buffered chunk before reporting completion."""
    for chunk in batch.chunks:
        sink.write(chunk)
    return len(batch.chunks)
