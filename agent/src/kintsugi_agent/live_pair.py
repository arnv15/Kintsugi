"""Assertions for the opt-in Research-to-Reuse live acceptance run."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


class LivePairError(AssertionError):
    """A paid live pair did not satisfy the issue #6 acceptance contract."""


def validate_live_pair(
    events: Iterable[Mapping[str, Any]],
    research_run_id: str,
    reuse_run_id: str,
) -> dict[str, str | int]:
    """Validate the observable Research-then-Reuse path and return its summary."""
    histories = {
        run_id: [event for event in events if event.get("run_id") == run_id]
        for run_id in (research_run_id, reuse_run_id)
    }
    research = histories[research_run_id]
    reuse = histories[reuse_run_id]
    if not research or not reuse:
        raise LivePairError("both live Runs must append events")

    _require_decision(research, "research", research_run_id)
    _require_decision(reuse, "reuse", reuse_run_id)
    _require_pass(research, research_run_id)
    _require_pass(reuse, reuse_run_id)

    research_sources = _count(research, "source_read")
    reuse_sources = _count(reuse, "source_read")
    if research_sources < 1:
        raise LivePairError("the Research Run must append at least one source_read")
    if reuse_sources != 0:
        raise LivePairError("the Reuse Run must append zero source_read events")

    published = _last(research, "skill_published")
    reused = _last(reuse, "skill_reused")
    if published is None:
        raise LivePairError("the green Research Run must publish a Skill")
    if reused is None:
        raise LivePairError("the Reuse Run must install and reuse a Skill")

    published_id = published.get("skill_id")
    reused_id = reused.get("skill_id")
    if not isinstance(published_id, str) or not published_id:
        raise LivePairError("skill_published must identify the published Skill")
    if reused_id != published_id:
        raise LivePairError("the second Run must reuse the first Run's Skill")

    return {
        "skill_id": published_id,
        "research_sources": research_sources,
        "reuse_sources": reuse_sources,
    }


def _require_decision(
    events: list[Mapping[str, Any]],
    expected: str,
    run_id: str,
) -> None:
    queried = _last(events, "registry_queried")
    if queried is None or queried.get("decision") != expected:
        raise LivePairError(
            f"Run '{run_id}' must receive Registry decision '{expected}'"
        )


def _require_pass(events: list[Mapping[str, Any]], run_id: str) -> None:
    finished = _last(events, "run_finished")
    if finished is None or finished.get("outcome") != "passed":
        raise LivePairError(f"Run '{run_id}' must finish with outcome 'passed'")


def _last(
    events: list[Mapping[str, Any]],
    event_type: str,
) -> Mapping[str, Any] | None:
    return next(
        (event for event in reversed(events) if event.get("type") == event_type),
        None,
    )


def _count(events: list[Mapping[str, Any]], event_type: str) -> int:
    return sum(event.get("type") == event_type for event in events)
