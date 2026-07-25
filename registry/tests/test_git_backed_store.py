"""The Skill directory as a shared git repository.

ADR-0001 treats the Registry as reachable by any agent on any machine. A
directory on one laptop is not that, so when the Skill directory is a git
working tree the Registry keeps it in step with its remote: it refreshes on
start, and a published Skill is committed and pushed.

The "remote" throughout is a bare repo in tmp_path. These tests never touch the
network.
"""

import subprocess
from pathlib import Path

import pytest

from kintsugi_registry.registry import SkillRegistry
from kintsugi_registry.sync import ensure_clone

from .conftest import MUTABLE_DEFAULT_SKILL

MATCHING_HYPOTHESIS = (
    "a mutable list is used as a default parameter value so it persists across calls"
)


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """A bare repo standing in for the shared Skills repo on GitHub."""
    path = tmp_path / "kintsugi-skills.git"
    path.mkdir()
    git("init", "--bare", "--initial-branch=main", cwd=path)
    return path


@pytest.fixture
def clone(tmp_path: Path, remote: Path) -> Path:
    path = tmp_path / "clone"
    git("clone", str(remote), str(path), cwd=tmp_path)
    return path


def files_on_the_remote(remote: Path, tmp_path: Path, name: str = "check") -> list[str]:
    """Everything committed on the remote's main branch, as a fresh observer sees it."""
    inspection = tmp_path / name
    git("clone", str(remote), str(inspection), cwd=tmp_path)
    listing = git("ls-files", cwd=inspection)
    return sorted(line for line in listing.splitlines() if line)


def test_a_published_skill_is_pushed_to_the_shared_repo(
    clone: Path, remote: Path, tmp_path: Path
) -> None:
    registry = SkillRegistry(skills_dir=clone)

    result = registry.publish_skill(**MUTABLE_DEFAULT_SKILL)

    assert result["published"] is True
    assert result["sync"]["pushed"] is True
    assert files_on_the_remote(remote, tmp_path) == ["mutable-default-argument/SKILL.md"]


def test_the_commit_records_who_published_the_skill(clone: Path) -> None:
    registry = SkillRegistry(skills_dir=clone)

    registry.publish_skill(**MUTABLE_DEFAULT_SKILL)

    subject = git("log", "-1", "--format=%s", cwd=clone)
    author = git("log", "-1", "--format=%an", cwd=clone)
    assert "mutable-default-argument" in subject
    assert author == "kintsugi-agent"


def test_a_skill_published_by_one_agent_is_found_by_another_after_it_refreshes(
    clone: Path, tmp_path: Path, remote: Path
) -> None:
    """The whole point of ADR-0001: a second agent, on its own clone, reuses it."""
    git("clone", str(remote), str(tmp_path / "second"), cwd=tmp_path)
    publisher = SkillRegistry(skills_dir=clone)
    consumer = SkillRegistry(skills_dir=tmp_path / "second")
    assert consumer.search_skills(MATCHING_HYPOTHESIS)["decision"] == "research"

    publisher.publish_skill(**MUTABLE_DEFAULT_SKILL)
    consumer.refresh()

    assert consumer.search_skills(MATCHING_HYPOTHESIS)["decision"] == "reuse"


def test_a_skill_survives_locally_when_the_push_fails(clone: Path) -> None:
    """A network problem must cost the push, never the Skill."""
    git("remote", "set-url", "origin", str(clone / "does-not-exist"), cwd=clone)
    registry = SkillRegistry(skills_dir=clone)

    result = registry.publish_skill(**MUTABLE_DEFAULT_SKILL)

    assert result["published"] is True
    assert result["sync"]["pushed"] is False
    assert result["sync"]["detail"]
    assert registry.get_skill("mutable-default-argument")["name"] == "Mutable default argument"


def test_a_first_run_clones_the_shared_repo_so_setup_is_one_variable(
    remote: Path, tmp_path: Path
) -> None:
    fresh_machine = tmp_path / "somebody-elses-laptop" / "skills"
    seed = SkillRegistry(skills_dir=_clone_of(remote, tmp_path, "seed"))
    seed.publish_skill(**MUTABLE_DEFAULT_SKILL)

    ensure_clone(fresh_machine, str(remote))

    assert SkillRegistry(skills_dir=fresh_machine).search_skills(
        MATCHING_HYPOTHESIS
    )["decision"] == "reuse"


def test_cloning_leaves_an_existing_clone_alone(clone: Path, remote: Path) -> None:
    detail = ensure_clone(clone, str(remote))

    assert "existing clone" in detail


def _clone_of(remote: Path, tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    git("clone", str(remote), str(path), cwd=tmp_path)
    return path


def test_a_plain_directory_still_works_with_no_git_anywhere(registry: SkillRegistry) -> None:
    result = registry.publish_skill(**MUTABLE_DEFAULT_SKILL)

    assert result["published"] is True
    assert result["sync"]["pushed"] is False
    assert registry.list_skills()["count"] == 1


def test_refreshing_a_plain_directory_is_harmless(registry: SkillRegistry) -> None:
    registry.publish_skill(**MUTABLE_DEFAULT_SKILL)

    registry.refresh()

    assert registry.list_skills()["count"] == 1


def test_a_nested_skill_directory_does_not_sync_through_its_parent_repo(
    clone: Path, remote: Path, tmp_path: Path
) -> None:
    (clone / "README.md").write_text("Parent repository\n", encoding="utf-8")
    git("add", "README.md", cwd=clone)
    git(
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "-m",
        "Seed parent",
        cwd=clone,
    )
    git("push", cwd=clone)
    parent_head = git("rev-parse", "HEAD", cwd=clone)
    nested_skills = clone / ".kintsugi" / "rehearsals" / "dst-pair" / "skills"
    nested_skills.mkdir(parents=True)
    registry = SkillRegistry(skills_dir=nested_skills)

    result = registry.publish_skill(**MUTABLE_DEFAULT_SKILL)

    assert result["sync"]["pushed"] is False
    assert git("rev-parse", "HEAD", cwd=clone) == parent_head
    assert files_on_the_remote(remote, tmp_path) == ["README.md"]
