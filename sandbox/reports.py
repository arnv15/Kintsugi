"""Worked-time reporting."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ShiftWindow:
    started_at: datetime
    ended_at: datetime


def shift_duration(window: ShiftWindow) -> timedelta:
    """Return the real elapsed duration of a completed shift."""
    if window.started_at.tzinfo is None or window.ended_at.tzinfo is None:
        raise ValueError("shift endpoints must be timezone-aware")

    return window.ended_at - window.started_at
