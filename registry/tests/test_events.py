"""What the Registry writes to its event log, and what it refuses to claim.

These assert at the Registry's tool boundary and then read the log file, because
the log *is* the observable output under test — an operator and a dashboard read
nothing else.
"""

import json
from pathlib import Path

import pytest

from kintsugi_registry.events import (
    EventLog,
    InvalidEvent,
    NoEventLog,
    build_event_log,
    resolve_events_path,
)
from kintsugi_registry.registry import SkillRegistry

from .conftest import MUTABLE_DEFAULT_SKILL


@pytest.fixture
def events_path(tmp_path: Path) -> Path:
    return tmp_path / "events.jsonl"


@pytest.fixture
def logging_registry(skills_dir: Path, events_path: Path) -> SkillRegistry:
    return SkillRegistry(
        skills_dir=skills_dir,
        events=EventLog(events_path, "session-1"),
    )


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_a_registry_with_no_log_configured_records_nothing(
    skills_dir: Path, events_path: Path
) -> None:
    registry = SkillRegistry(skills_dir=skills_dir)

    registry.publish_skill(**MUTABLE_DEFAULT_SKILL)
    registry.search_skills("a mutable object is used as a default parameter value")

    assert not events_path.exists()


def test_searching_records_the_decision_the_registry_made(
    logging_registry: SkillRegistry, events_path: Path
) -> None:
    logging_registry.publish_skill(**MUTABLE_DEFAULT_SKILL)
    logging_registry.search_skills(
        "a mutable list is used as a default parameter value so it persists across calls"
    )

    queried = [event for event in read_events(events_path) if event["type"] == "registry_queried"]
    assert len(queried) == 1
    assert queried[0]["decision"] == "reuse"
    assert queried[0]["skill_id"] == "mutable-default-argument"
    assert queried[0]["top_score"] >= logging_registry.threshold


def test_a_search_with_no_match_records_a_research_decision(
    logging_registry: SkillRegistry, events_path: Path
) -> None:
    logging_registry.search_skills(
        "the retry loop reads an environment variable once at import time"
    )

    queried = [event for event in read_events(events_path) if event["type"] == "registry_queried"]
    assert [event["decision"] for event in queried] == ["research"]
    assert queried[0]["skill_id"] is None


def test_a_refused_query_records_nothing_because_no_decision_was_made(
    logging_registry: SkillRegistry, events_path: Path
) -> None:
    with pytest.raises(Exception):
        logging_registry.search_skills("Traceback (most recent call last): line 42")

    assert read_events(events_path) == []


def test_publishing_and_retrieving_are_recorded_as_separate_facts(
    logging_registry: SkillRegistry, events_path: Path
) -> None:
    logging_registry.publish_skill(**MUTABLE_DEFAULT_SKILL)
    logging_registry.get_skill("mutable-default-argument")

    types = [event["type"] for event in read_events(events_path)]
    assert types == ["skill_published", "skill_retrieved"]


def test_a_refused_publish_records_nothing(
    logging_registry: SkillRegistry, events_path: Path
) -> None:
    logging_registry.publish_skill(
        name="", description="", aliases=[], body=""
    )

    assert read_events(events_path) == []


def test_every_event_carries_the_session_and_a_rising_sequence(
    logging_registry: SkillRegistry, events_path: Path
) -> None:
    logging_registry.publish_skill(**MUTABLE_DEFAULT_SKILL)
    logging_registry.get_skill("mutable-default-argument")
    logging_registry.search_skills("a mutable default parameter is shared across calls")

    events = read_events(events_path)
    assert [event["run_id"] for event in events] == ["session-1"] * 3
    assert [event["seq"] for event in events] == [1, 2, 3]
    assert all(event["ts"].endswith("Z") for event in events)


def test_the_registry_may_not_record_something_it_cannot_observe(
    events_path: Path,
) -> None:
    log = EventLog(events_path, "session-1")

    with pytest.raises(InvalidEvent):
        log.append("tests_run", passed=1, failed=0, output_tail="OK")


def test_an_unconfigured_path_builds_a_log_that_writes_nothing() -> None:
    assert isinstance(build_event_log(None, "session-1"), NoEventLog)
    assert build_event_log(None, "session-1").append("skill_published") is None


def test_the_events_path_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert resolve_events_path() is None

    monkeypatch.setenv("KINTSUGI_EVENTS_PATH", str(tmp_path / "log.jsonl"))
    assert resolve_events_path() == tmp_path / "log.jsonl"
