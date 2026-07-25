"""Searching the Registry with a Root Cause Hypothesis.

The hypotheses below are deliberately *not* copies of the Skill text they are
expected to match — the whole point of ADR-0003 is that a second bug of the same
Root Cause Class is described in different words.
"""

from kintsugi_registry.registry import SkillRegistry


def test_hypothesis_matching_a_skill_description_returns_reuse_and_that_skill(
    populated_registry: SkillRegistry,
) -> None:
    result = populated_registry.search_skills(
        "a mutable list is used as a default parameter value so it persists across calls"
    )

    assert result["decision"] == "reuse"
    assert result["matches"][0]["id"] == "mutable-default-argument"


def test_hypothesis_matching_a_skill_alias_returns_reuse_and_that_skill(
    populated_registry: SkillRegistry,
) -> None:
    result = populated_registry.search_skills(
        "the default argument seems to be keeping values from a previous call"
    )

    assert result["decision"] == "reuse"
    best = result["matches"][0]
    assert best["id"] == "mutable-default-argument"
    assert best["matched_on"] == "default argument keeps values from a previous call"


def test_hypothesis_with_no_matching_skill_returns_research(
    populated_registry: SkillRegistry,
) -> None:
    result = populated_registry.search_skills(
        "the retry loop reads an environment variable once at import time, "
        "so a later change to it is never picked up"
    )

    assert result["decision"] == "research"
    assert result["matches"] == []


def test_an_empty_registry_sends_every_hypothesis_down_the_research_path(
    registry: SkillRegistry,
) -> None:
    result = registry.search_skills(
        "a mutable list is used as a default parameter value so it persists across calls"
    )

    assert result["decision"] == "research"
    assert result["matches"] == []


def test_a_hypothesis_reaches_the_skill_for_its_own_root_cause_class_not_the_other_one(
    populated_registry: SkillRegistry,
) -> None:
    result = populated_registry.search_skills(
        "two floating point numbers are compared with exact equality"
    )

    assert result["decision"] == "reuse"
    assert [match["id"] for match in result["matches"]] == [
        "exact-equality-comparison-of-floating-point-numbers"
    ]
