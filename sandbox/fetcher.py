"""Concurrent resource fetching."""

import asyncio
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PayloadSummary:
    received: int
    total_characters: int


def summarize_payloads(payloads: Sequence[str]) -> PayloadSummary:
    """Summarize a completed set of fetched payloads."""
    return PayloadSummary(
        received=len(payloads),
        total_characters=sum(len(payload) for payload in payloads),
    )


def nonempty_payloads(payloads: Sequence[str]) -> list[str]:
    """Discard empty successful responses while retaining response order."""
    return [payload for payload in payloads if payload]


async def fetch_all(requests: Sequence[Awaitable[str]]) -> list[str]:
    """Return every payload, or propagate a request failure."""
    results = await asyncio.gather(*requests, return_exceptions=True)
    return [result for result in results if not isinstance(result, BaseException)]
