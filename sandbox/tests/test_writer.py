import asyncio
import unittest

from sandbox.writer import WriteBatch, flush


class MemorySink:
    def __init__(self) -> None:
        self.received: list[bytes] = []

    async def write(self, payload: bytes) -> None:
        await asyncio.sleep(0)
        self.received.append(payload)


class BufferedWriteTests(unittest.TestCase):
    def test_flush_returns_only_after_all_binary_chunks_are_durable(self) -> None:
        sink = MemorySink()
        batch = WriteBatch(chunks=(b"header", b"body"))

        written_count = asyncio.run(flush(batch, sink))

        self.assertEqual(2, written_count)
        self.assertEqual([b"header", b"body"], sink.received)


if __name__ == "__main__":
    unittest.main()
