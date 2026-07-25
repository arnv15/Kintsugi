"""Append-only, schema-checked event history for one Kintsugi Run."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


EVENT_FIELDS: dict[str, tuple[str, ...]] = {
    "run_started": ("bug_id", "root_cause_class"),
    "hypothesis_formed": ("text",),
    "registry_queried": ("decision", "top_score", "skill_id"),
    "source_read": ("url", "title"),
    "strategy_recorded": ("text", "sources"),
    "patch_applied": ("files_touched",),
    "tests_run": ("passed", "failed", "output_tail"),
    "skill_published": ("skill_id", "name"),
    "skill_reused": ("skill_id", "name"),
    "run_finished": (
        "outcome",
        "tokens",
        "cost_usd",
        "seconds",
        "sources_count",
    ),
}


class InvalidEvent(ValueError):
    """An event does not conform to the accepted event-log contract."""


class EventLog:
    """The sole append-only writer for a Run's event stream."""

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = Path(path)
        self.run_id = run_id
        self._lock = asyncio.Lock()
        self._events: list[dict[str, Any]] = []
        self._retrieved_skills: dict[str, dict[str, Any]] = {}

    async def append(self, event_type: str, **fields: Any) -> dict[str, Any]:
        """Validate and append one event, preserving sequence order."""
        async with self._lock:
            event = {
                "ts": datetime.now(UTC).isoformat(timespec="milliseconds").replace(
                    "+00:00", "Z"
                ),
                "run_id": self.run_id,
                "seq": len(self._events) + 1,
                "type": event_type,
                **fields,
            }
            validate_event(event)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(event, separators=(",", ":")) + "\n")
            self._events.append(event)
            return dict(event)

    async def contains(self, event_type: str) -> bool:
        """Whether this Run has already recorded an event of the given type."""
        async with self._lock:
            return any(event["type"] == event_type for event in self._events)

    async def events(self) -> list[dict[str, Any]]:
        """Return a stable copy of the current in-memory Run history."""
        async with self._lock:
            return [dict(event) for event in self._events]

    async def latest(self, event_type: str) -> dict[str, Any] | None:
        """Return the most recently appended event of one type."""
        async with self._lock:
            for event in reversed(self._events):
                if event["type"] == event_type:
                    return dict(event)
        return None

    async def current_verification_passed(self) -> bool:
        """Whether the latest patch state is covered by a passing verification."""
        async with self._lock:
            latest_tests_index = next(
                (
                    index
                    for index in range(len(self._events) - 1, -1, -1)
                    if self._events[index]["type"] == "tests_run"
                ),
                None,
            )
            if latest_tests_index is None:
                return False
            latest_tests = self._events[latest_tests_index]
            changed_afterward = any(
                event["type"] == "patch_applied"
                for event in self._events[latest_tests_index + 1 :]
            )
            return (
                latest_tests["passed"] > 0
                and latest_tests["failed"] == 0
                and not changed_afterward
            )

    async def verification_attempts(self) -> int:
        """Count verification commands that actually executed."""
        async with self._lock:
            return sum(event["type"] == "tests_run" for event in self._events)

    async def source_urls(self) -> set[str]:
        """Return only sources actually observed through WebFetch."""
        async with self._lock:
            return {
                str(event["url"])
                for event in self._events
                if event["type"] == "source_read"
            }

    async def source_count(self) -> int:
        """Count sources read during this Run."""
        async with self._lock:
            return sum(event["type"] == "source_read" for event in self._events)

    async def remember_retrieved_skill(self, payload: dict[str, Any]) -> bool:
        """Retain the Registry's authoritative get_skill response for installation."""
        skill_id = payload.get("id")
        name = payload.get("name")
        document = payload.get("document")
        sources = payload.get("sources")
        if (
            not isinstance(skill_id, str)
            or not skill_id
            or not isinstance(name, str)
            or not name
            or not isinstance(document, str)
            or not document
            or not isinstance(sources, list)
            or not sources
            or any(not isinstance(source, str) or not source for source in sources)
        ):
            return False
        async with self._lock:
            self._retrieved_skills[skill_id] = {
                "id": skill_id,
                "name": name,
                "document": document,
                "sources": list(sources),
            }
        return True

    async def retrieved_skill(self, skill_id: str) -> dict[str, Any] | None:
        """Return one exact Registry response retained by the PostToolUse hook."""
        async with self._lock:
            skill = self._retrieved_skills.get(skill_id)
            return dict(skill) if skill is not None else None


def validate_event(event: dict[str, Any]) -> None:
    """Validate the fields shared with the fixture and event server."""
    for field in ("ts", "run_id", "seq", "type"):
        if field not in event:
            raise InvalidEvent(f"event is missing required field '{field}'")

    event_type = event["type"]
    if event_type not in EVENT_FIELDS:
        raise InvalidEvent(f"unknown event type '{event_type}'")

    missing = [field for field in EVENT_FIELDS[event_type] if field not in event]
    if missing:
        raise InvalidEvent(
            f"{event_type} is missing required field(s): {', '.join(missing)}"
        )

    if not isinstance(event["ts"], str) or not event["ts"]:
        raise InvalidEvent("event.ts must be a non-empty ISO timestamp")
    if not isinstance(event["run_id"], str) or not event["run_id"]:
        raise InvalidEvent("event.run_id must be a non-empty string")
    if (
        not isinstance(event["seq"], int)
        or isinstance(event["seq"], bool)
        or event["seq"] < 1
    ):
        raise InvalidEvent("event.seq must be a positive integer")

    _require_strings(
        event,
        {
            "run_started": ("bug_id", "root_cause_class"),
            "hypothesis_formed": ("text",),
            "source_read": ("url", "title"),
            "strategy_recorded": ("text",),
            "tests_run": ("output_tail",),
            "skill_published": ("skill_id", "name"),
            "skill_reused": ("skill_id", "name"),
        }.get(event_type, ()),
    )

    if event_type == "registry_queried" and event["decision"] not in {
        "research",
        "reuse",
    }:
        raise InvalidEvent("registry_queried.decision must be research or reuse")
    if event_type == "registry_queried":
        if not _is_number(event["top_score"]):
            raise InvalidEvent("registry_queried.top_score must be a number")
        if event["skill_id"] is not None and not isinstance(event["skill_id"], str):
            raise InvalidEvent("registry_queried.skill_id must be a string or null")
        if event["decision"] == "reuse" and not event["skill_id"]:
            raise InvalidEvent("a Reuse decision must identify its Skill")

    if event_type == "strategy_recorded":
        _require_string_list(event, "sources", allow_empty=False)
    if event_type == "patch_applied":
        _require_string_list(event, "files_touched", allow_empty=False)

    if event_type == "tests_run":
        _require_non_negative_integers(event, ("passed", "failed"))
    if event_type == "run_finished" and event["outcome"] not in {
        "passed",
        "failed",
    }:
        raise InvalidEvent("run_finished.outcome must be passed or failed")
    if event_type == "run_finished":
        if event["tokens"] is not None:
            _require_non_negative_integers(event, ("tokens",))
        _require_non_negative_integers(event, ("sources_count",))
        if event["cost_usd"] is not None and (
            not _is_number(event["cost_usd"]) or event["cost_usd"] < 0
        ):
            raise InvalidEvent(
                "run_finished.cost_usd must be a non-negative number or null"
            )
        if not _is_number(event["seconds"]) or event["seconds"] < 0:
            raise InvalidEvent("run_finished.seconds must be a non-negative number")


def _require_strings(event: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        if not isinstance(event[field], str) or not event[field]:
            raise InvalidEvent(f"{event['type']}.{field} must be a non-empty string")


def _require_string_list(
    event: dict[str, Any], field: str, allow_empty: bool
) -> None:
    value = event[field]
    if (
        not isinstance(value, list)
        or (not value and not allow_empty)
        or any(not isinstance(item, str) or not item for item in value)
    ):
        qualifier = "" if allow_empty else " non-empty"
        raise InvalidEvent(
            f"{event['type']}.{field} must be a{qualifier} list of strings"
        )


def _require_non_negative_integers(
    event: dict[str, Any], fields: tuple[str, ...]
) -> None:
    for field in fields:
        value = event[field]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise InvalidEvent(
                f"{event['type']}.{field} must be a non-negative integer"
            )


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
