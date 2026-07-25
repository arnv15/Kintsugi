"""Publishing a Skill, and reading it back out of the Registry."""

from pathlib import Path

from kintsugi_registry.registry import SkillRegistry

from .conftest import MUTABLE_DEFAULT_SKILL


def test_published_skill_is_immediately_visible_to_list_skills_and_get_skill(
    registry: SkillRegistry,
) -> None:
    result = registry.publish_skill(**MUTABLE_DEFAULT_SKILL)

    assert result["published"] is True
    skill_id = result["skill_id"]

    listed = registry.list_skills()
    assert [entry["id"] for entry in listed["skills"]] == [skill_id]
    assert listed["skills"][0]["name"] == "Mutable default argument"

    fetched = registry.get_skill(skill_id)
    assert fetched["name"] == "Mutable default argument"
    assert fetched["aliases"] == MUTABLE_DEFAULT_SKILL["aliases"]
    assert fetched["sources"] == MUTABLE_DEFAULT_SKILL["sources"]
    assert fetched["published_by"] == "kintsugi-agent"
    assert "sentinel" in fetched["body"]


def test_a_well_formed_skill_publishes_without_warnings(registry: SkillRegistry) -> None:
    assert registry.publish_skill(**MUTABLE_DEFAULT_SKILL)["warnings"] == []


def test_republishing_the_same_root_cause_class_replaces_the_stored_skill(
    registry: SkillRegistry,
) -> None:
    first = registry.publish_skill(**MUTABLE_DEFAULT_SKILL)
    assert first["replaced"] is False

    second = registry.publish_skill(
        **{**MUTABLE_DEFAULT_SKILL, "body": "A better explanation of the same class.\n"}
    )

    assert second["replaced"] is True
    assert second["skill_id"] == first["skill_id"]
    assert registry.list_skills()["count"] == 1
    assert registry.get_skill(first["skill_id"])["body"].startswith("A better explanation")


def test_a_skill_without_sources_or_provenance_publishes_but_says_what_is_missing(
    registry: SkillRegistry,
) -> None:
    thin = {**MUTABLE_DEFAULT_SKILL, "aliases": ["state persists across calls"]}
    del thin["sources"]
    del thin["published_by"]

    result = registry.publish_skill(**thin)

    assert result["published"] is True
    warnings = " ".join(result["warnings"])
    assert "alias" in warnings
    assert "sources" in warnings
    assert "published_by" in warnings


def test_a_skill_with_no_description_is_refused_because_nothing_could_match_it(
    registry: SkillRegistry,
) -> None:
    result = registry.publish_skill(**{**MUTABLE_DEFAULT_SKILL, "description": "  "})

    assert result["published"] is False
    assert "description" in result["feedback"]
    assert registry.list_skills()["count"] == 0


def test_a_skill_document_that_cannot_be_read_is_reported_rather_than_breaking_the_registry(
    registry: SkillRegistry, skills_dir: Path
) -> None:
    registry.publish_skill(**MUTABLE_DEFAULT_SKILL)
    hand_edited = skills_dir / "half-written-skill"
    hand_edited.mkdir()
    (hand_edited / "SKILL.md").write_text("no frontmatter here\n", encoding="utf-8")

    listed = registry.list_skills()

    assert [entry["id"] for entry in listed["skills"]] == ["mutable-default-argument"]
    assert listed["unreadable"] == ["half-written-skill"]
    assert (
        registry.search_skills(
            "a mutable list is used as a default parameter value so it persists across calls"
        )["decision"]
        == "reuse"
    )
