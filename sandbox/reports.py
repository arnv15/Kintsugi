"""Worked-time reporting."""

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ShiftWindow:
    started_at: datetime
    ended_at: datetime

    @property
    def crosses_calendar_date(self) -> bool:
        return self.started_at.date() != self.ended_at.date()

    @property
    def employee_day(self) -> str:
        return self.started_at.strftime("%Y-%m-%d")


def shift_reference(employee_id: str, window: ShiftWindow) -> str:
    """Return the stable key used to join a shift into a report."""
    return f"{employee_id}:{window.employee_day}"


def shift_duration(window: ShiftWindow) -> timedelta:
    """Return the real elapsed duration of a completed shift."""
    if window.started_at.tzinfo is None or window.ended_at.tzinfo is None:
        raise ValueError("shift endpoints must be timezone-aware")

    return window.ended_at - window.started_at
