"""The append-only record of what the Registry itself observed.

ADR-0007 split the system so that the thing being measured never grades its own
work: something records facts, something else reshapes them, and only the
dashboard draws conclusions. That split survives the removal of the bundled
runtime — what changes is who does the recording. The Registry is now the only
component present in every Run, because it is the only component every agent
connects to, so it is the only honest place left to write the log from.

It can therefore record strictly less than the old runtime could. A tool call is
all it sees: it never observes an edit, a test result, a token count, or whether
a fix ever went green. Those event types are simply absent rather than guessed
at, and `skill_retrieved` is deliberately not called `skill_reused` — the
Registry watched a document leave, which is not the same claim as a Skill having
produced a passing fix.

Writing is opt-in via `KINTSUGI_EVENTS_PATH`. Unset, the Registry keeps no log
at all, because a shared server should not accumulate a record of every query an
operator never asked it to keep.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVENTS_PATH_ENV_VAR = "KINTSUGI_EVENTS_PATH"

EVENT_FIELDS: dict[str, tuple[str, ...]] = {
    "registry_queried": ("decision", "top_score", "skill_id"),
    "skill_retrieved": ("skill_id", "name"),
    "skill_published": ("skill_id", "name"),
}
"""Every event type the Registry can witness first-hand, and its required fields."""


class InvalidEvent(ValueError):
    """An event does not conform to the accepted event-log contract."""


class NoEventLog:
    """No log is configured, so nothing is recorded.

    A null object rather than a `None` the Registry has to keep checking: the
    difference between a logging deployment and a quiet one belongs here, not in
    branches scattered through every tool method.
    """

    path: Path | None = None

    def append(self, event_type: str, **fields: Any) -> dict[str, Any] | None:
        return None


class EventLog:
    """The sole append-only writer for one Registry session's event stream."""

    def __init__(self, path: Path, session_id: str) -> None:
        self.path = Path(path)
        self.session_id = session_id
        self._seq = 0

    def append(self, event_type: str, **fields: Any) -> dict[str, Any]:
        """Validate and append one event, preserving sequence order.

        `run_id` carries the session id rather than a Run id. The field keeps its
        name so an existing event server and dashboard read this log unchanged;
        what it identifies is now one agent's connection to the Registry, since
        the Registry cannot see where a Run starts or ends.
        """
        self._seq += 1
        event = {
            "ts": datetime.now(UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "run_id": self.session_id,
            "seq": self._seq,
            "type": event_type,
            **fields,
        }
        validate_event(event)

        # Reopened per append, and one line per write, so two agents connected at
        # once interleave whole events instead of corrupting each other's.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, separators=(",", ":")) + "\n")
        return event


def validate_event(event: dict[str, Any]) -> None:
    """Reject anything that would not round-trip through the event server."""
    for field in ("ts", "run_id", "seq", "type"):
        if field not in event:
            raise InvalidEvent(f"event is missing required field '{field}'")

    event_type = event["type"]
    if event_type not in EVENT_FIELDS:
        raise InvalidEvent(
            f"unknown event type '{event_type}'; the Registry may only record "
            f"what it observes directly: {', '.join(sorted(EVENT_FIELDS))}"
        )

    missing = [field for field in EVENT_FIELDS[event_type] if field not in event]
    if missing:
        raise InvalidEvent(
            f"{event_type} is missing required field(s): {', '.join(missing)}"
        )

    if not isinstance(event["run_id"], str) or not event["run_id"]:
        raise InvalidEvent("event.run_id must be a non-empty string")
    if (
        not isinstance(event["seq"], int)
        or isinstance(event["seq"], bool)
        or event["seq"] < 1
    ):
        raise InvalidEvent("event.seq must be a positive integer")

    if event_type == "registry_queried":
        if event["decision"] not in {"research", "reuse"}:
            raise InvalidEvent("registry_queried.decision must be research or reuse")
        if isinstance(event["top_score"], bool) or not isinstance(
            event["top_score"], (int, float)
        ):
            raise InvalidEvent("registry_queried.top_score must be a number")
        if event["skill_id"] is not None and not isinstance(event["skill_id"], str):
            raise InvalidEvent("registry_queried.skill_id must be a string or null")
        if event["decision"] == "reuse" and not event["skill_id"]:
            raise InvalidEvent("a Reuse decision must identify its Skill")
    else:
        for field in ("skill_id", "name"):
            if not isinstance(event[field], str) or not event[field]:
                raise InvalidEvent(f"{event_type}.{field} must be a non-empty string")


def resolve_events_path(explicit: str | Path | None = None) -> Path | None:
    """Pick the event log to append to, or None when logging is off."""
    if explicit is not None:
        return Path(explicit).expanduser()

    from_env = os.environ.get(EVENTS_PATH_ENV_VAR)
    return Path(from_env).expanduser() if from_env else None


def build_event_log(
    path: Path | None, session_id: str
) -> EventLog | NoEventLog:
    """Pick a logging strategy from whether a path was configured."""
    return NoEventLog() if path is None else EventLog(path, session_id)
