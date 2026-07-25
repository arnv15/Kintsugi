"""Concurrent resource fetching."""

import asyncio
from collections.abc import Awaitable, Sequence


async def fetch_all(requests: Sequence[Awaitable[str]]) -> list[str]:
    """Return every payload, or propagate a request failure."""
    results = await asyncio.gather(*requests, return_exceptions=True)
    return [result for result in results if not isinstance(result, BaseException)]
