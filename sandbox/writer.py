"""Buffered asynchronous writes."""

from dataclasses import dataclass
from typing import Protocol


class ByteSink(Protocol):
    async def write(self, payload: bytes) -> None: ...


@dataclass(frozen=True)
class WriteBatch:
    chunks: tuple[bytes, ...]

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def byte_count(self) -> int:
        return sum(len(chunk) for chunk in self.chunks)

    @property
    def is_empty(self) -> bool:
        return not self.chunks


async def flush(batch: WriteBatch, sink: ByteSink) -> int:
    """Persist every buffered chunk before reporting completion."""
    for chunk in batch.chunks:
        sink.write(chunk)
    return batch.chunk_count
