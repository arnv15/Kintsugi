"""Clearing the Registry between rehearsals.

Issue #8 rehearses the Research-Path-then-Reuse-Path sequence repeatedly, so a
Skill published during one rehearsal must not still be there when the next
rehearsal expects its first Run to take the Research Path. Clearing is
deliberately not an MCP tool — see `test_mcp_server.py`.
"""

from pathlib import Path

import pytest

from kintsugi_registry import cli
from kintsugi_registry.registry import SkillRegistry

HYPOTHESIS_THAT_MATCHES_A_STORED_SKILL = (
    "a mutable list is used as a default parameter value so it persists across calls"
)


def test_clearing_removes_every_skill(populated_registry: SkillRegistry) -> None:
    assert populated_registry.list_skills()["count"] == 2

    removed = populated_registry.clear()

    assert sorted(removed) == [
        "exact-equality-comparison-of-floating-point-numbers",
        "mutable-default-argument",
    ]
    remaining = populated_registry.list_skills()
    assert remaining["count"] == 0
    assert remaining["skills"] == []


def test_a_cleared_registry_sends_a_previously_matching_hypothesis_back_to_research(
    populated_registry: SkillRegistry,
) -> None:
    assert (
        populated_registry.search_skills(HYPOTHESIS_THAT_MATCHES_A_STORED_SKILL)["decision"]
        == "reuse"
    )

    populated_registry.clear()

    assert (
        populated_registry.search_skills(HYPOTHESIS_THAT_MATCHES_A_STORED_SKILL)["decision"]
        == "research"
    )


def test_clearing_leaves_anything_that_is_not_a_skill_alone(
    populated_registry: SkillRegistry, skills_dir: Path
) -> None:
    (skills_dir / "README.md").write_text("Notes about this directory\n", encoding="utf-8")
    (skills_dir / "scratch").mkdir()

    populated_registry.clear()

    assert (skills_dir / "README.md").is_file()
    assert (skills_dir / "scratch").is_dir()


def test_the_clear_command_empties_the_registry(
    populated_registry: SkillRegistry, skills_dir: Path
) -> None:
    exit_code = cli.main(["clear", "--skills-dir", str(skills_dir), "--yes"])

    assert exit_code == 0
    assert populated_registry.list_skills()["count"] == 0


def test_the_clear_command_removes_nothing_unless_it_is_told_to(
    populated_registry: SkillRegistry, skills_dir: Path
) -> None:
    exit_code = cli.main(["clear", "--skills-dir", str(skills_dir)])

    assert exit_code != 0
    assert populated_registry.list_skills()["count"] == 2


def test_the_clear_command_can_report_what_it_would_remove(
    populated_registry: SkillRegistry, skills_dir: Path, capsys
) -> None:
    exit_code = cli.main(["clear", "--skills-dir", str(skills_dir), "--dry-run"])

    assert exit_code == 0
    assert "mutable-default-argument" in capsys.readouterr().out
    assert populated_registry.list_skills()["count"] == 2


def test_clearing_an_already_empty_registry_is_not_an_error(
    registry: SkillRegistry, skills_dir: Path
) -> None:
    assert registry.clear() == []
    assert cli.main(["clear", "--skills-dir", str(skills_dir), "--yes"]) == 0


def test_scope_command_creates_an_isolated_skill_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rehearsals_root = tmp_path / "rehearsals"

    exit_code = cli.main(
        [
            "scope",
            "dst-pair",
            "--rehearsals-root",
            str(rehearsals_root),
        ]
    )

    scoped_skills = rehearsals_root / "dst-pair" / "skills"
    assert exit_code == 0
    assert scoped_skills.is_dir()
    assert str(scoped_skills.resolve()) in capsys.readouterr().out


def test_scope_reset_removes_only_skills_in_the_selected_scope(
    tmp_path: Path,
) -> None:
    rehearsals_root = tmp_path / "rehearsals"
    selected = rehearsals_root / "dst-pair"
    other = rehearsals_root / "money-pair"
    selected_skill = selected / "skills" / "datetime-semantics"
    other_skill = other / "skills" / "decimal-money"
    selected_skill.mkdir(parents=True)
    other_skill.mkdir(parents=True)
    (selected_skill / "SKILL.md").write_text("---\nname: Date time\n---\n", encoding="utf-8")
    (other_skill / "SKILL.md").write_text("---\nname: Money\n---\n", encoding="utf-8")
    (selected / "events.jsonl").write_text('{"type":"run_started"}\n', encoding="utf-8")
    retained_run = selected / "runs" / "prior-run"
    retained_run.mkdir(parents=True)

    exit_code = cli.main(
        [
            "scope",
            "dst-pair",
            "--rehearsals-root",
            str(rehearsals_root),
            "--reset",
        ]
    )

    assert exit_code == 0
    assert not selected_skill.exists()
    assert (selected / "skills").is_dir()
    assert other_skill.is_dir()
    assert (selected / "events.jsonl").is_file()
    assert retained_run.is_dir()


def test_scope_reset_sends_a_prior_match_back_to_the_research_path(
    tmp_path: Path,
) -> None:
    rehearsals_root = tmp_path / "rehearsals"
    skills_dir = rehearsals_root / "dst-pair" / "skills"
    registry = SkillRegistry(skills_dir=skills_dir)
    registry.publish_skill(
        name="Mutable default argument",
        description=(
            "A mutable object is used as a default parameter value, so the same "
            "object is shared across every call to the function"
        ),
        aliases=["default argument keeps values from a previous call"],
        body="Build a new mutable object inside the function body.\n",
    )
    assert (
        registry.search_skills(HYPOTHESIS_THAT_MATCHES_A_STORED_SKILL)["decision"]
        == "reuse"
    )

    cli.main(
        [
            "scope",
            "dst-pair",
            "--rehearsals-root",
            str(rehearsals_root),
            "--reset",
        ]
    )

    assert (
        registry.search_skills(HYPOTHESIS_THAT_MATCHES_A_STORED_SKILL)["decision"]
        == "research"
    )


@pytest.mark.parametrize("scope", ["../shared", "nested/scope", ".", ".."])
def test_scope_command_rejects_unsafe_scope_names(
    tmp_path: Path, scope: str
) -> None:
    with pytest.raises(ValueError, match="safe single directory name"):
        cli.main(
            [
                "scope",
                scope,
                "--rehearsals-root",
                str(tmp_path / "rehearsals"),
            ]
        )


def test_scope_reset_rejects_a_symlinked_skill_directory(tmp_path: Path) -> None:
    rehearsals_root = tmp_path / "rehearsals"
    shared = tmp_path / "shared"
    shared_skill = shared / "valuable-skill"
    shared_skill.mkdir(parents=True)
    (shared_skill / "SKILL.md").write_text("---\nname: Keep me\n---\n", encoding="utf-8")
    scope = rehearsals_root / "dst-pair"
    scope.mkdir(parents=True)
    (scope / "skills").symlink_to(shared, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        cli.main(
            [
                "scope",
                "dst-pair",
                "--rehearsals-root",
                str(rehearsals_root),
                "--reset",
            ]
        )

    assert shared_skill.is_dir()


def test_scope_reset_unlinks_a_symlinked_skill_without_touching_its_target(
    tmp_path: Path,
) -> None:
    rehearsals_root = tmp_path / "rehearsals"
    skills_dir = rehearsals_root / "dst-pair" / "skills"
    skills_dir.mkdir(parents=True)
    shared_skill = tmp_path / "shared" / "valuable-skill"
    shared_skill.mkdir(parents=True)
    shared_document = shared_skill / "SKILL.md"
    shared_document.write_text("---\nname: Keep me\n---\n", encoding="utf-8")
    linked_skill = skills_dir / "linked-skill"
    linked_skill.symlink_to(shared_skill, target_is_directory=True)

    exit_code = cli.main(
        [
            "scope",
            "dst-pair",
            "--rehearsals-root",
            str(rehearsals_root),
            "--reset",
        ]
    )

    assert exit_code == 0
    assert not linked_skill.exists()
    assert shared_document.is_file()
