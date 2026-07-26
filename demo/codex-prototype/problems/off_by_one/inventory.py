"""A small seeded bug: an inclusive/exclusive slice boundary mistake."""

from __future__ import annotations


def last_n_orders(orders: list[str], n: int) -> list[str]:
    """Return the most recent `n` orders, oldest first."""
    return orders[-n:]
