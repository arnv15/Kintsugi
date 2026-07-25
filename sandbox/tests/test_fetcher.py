import asyncio
import unittest

from sandbox.fetcher import fetch_all


async def available_payload() -> str:
    return "catalog"


async def unavailable_payload() -> str:
    raise ConnectionError("inventory offline")


class ConcurrentFetchTests(unittest.TestCase):
    def test_batch_request_surfaces_a_failed_dependency(self) -> None:
        async def exercise() -> None:
            with self.assertRaisesRegex(ConnectionError, "inventory offline"):
                await fetch_all([available_payload(), unavailable_payload()])

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
