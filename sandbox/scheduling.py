"""Recurring schedule calculations."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class RunRecord:
    schedule_name: str
    ran_at: datetime

    @property
    def local_date_label(self) -> str:
        return self.ran_at.strftime("%Y-%m-%d")


def latest_run(records: list[RunRecord]) -> RunRecord:
    """Return the record representing the latest real instant."""
    if not records:
        raise ValueError("at least one run record is required")
    if any(record.ran_at.tzinfo is None for record in records):
        raise ValueError("run records must be timezone-aware")
    return max(records, key=lambda record: record.ran_at.astimezone(timezone.utc))


def next_run_at(previous_run: datetime) -> datetime:
    """Return tomorrow's run at the same local wall-clock time."""
    if previous_run.tzinfo is None:
        raise ValueError("previous_run must be timezone-aware")

    utc_candidate = previous_run.astimezone(timezone.utc) + timedelta(hours=24)
    return utc_candidate.astimezone(previous_run.tzinfo)
