"""Recurring schedule calculations."""

from datetime import datetime, timedelta, timezone


def next_run_at(previous_run: datetime) -> datetime:
    """Return tomorrow's run at the same local wall-clock time."""
    if previous_run.tzinfo is None:
        raise ValueError("previous_run must be timezone-aware")

    utc_candidate = previous_run.astimezone(timezone.utc) + timedelta(hours=24)
    return utc_candidate.astimezone(previous_run.tzinfo)
