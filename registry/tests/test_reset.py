"""Clearing the Registry between rehearsals.

Issue #8 rehearses the Research-Path-then-Reuse-Path sequence repeatedly, so a
Skill published during one rehearsal must not still be there when the next
rehearsal expects its first Run to take the Research Path. Clearing is
deliberately not an MCP tool — see `test_mcp_server.py`.
"""

from pathlib import Path

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
