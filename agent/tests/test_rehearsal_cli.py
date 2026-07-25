from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pytest

from kintsugi_agent.live_pair_cli import isolated_registry_environment
from kintsugi_agent.rehearsal_cli import run


def test_live_pair_disables_remote_sync_for_its_isolated_registry(
    tmp_path: Path,
) -> None:
    environment = isolated_registry_environment(tmp_path / "skills")

    assert environment == {
        "KINTSUGI_SKILLS_DIR": str(tmp_path / "skills"),
        "KINTSUGI_SKILLS_REMOTE": "",
    }


@pytest.mark.asyncio
async def test_rehearsal_resets_one_scope_then_runs_the_cold_warm_pair(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    resets: list[tuple[tuple[str, ...], Path, str]] = []
    pairs: list[argparse.Namespace] = []

    async def reset_scope(
        command: tuple[str, ...], rehearsals_root: Path, scope: str
    ) -> None:
        resets.append((command, rehearsals_root, scope))
        (rehearsals_root / scope / "skills").mkdir(parents=True, exist_ok=True)

    async def run_pair(arguments: argparse.Namespace) -> dict[str, Any]:
        pairs.append(arguments)
        artifacts = Path(arguments.artifacts_root) / str(arguments.pair_id)
        artifacts.mkdir(parents=True)
        return {
            "pair_id": arguments.pair_id,
            "outcome": "passed",
            "skill_id": "datetime-semantics",
            "research_sources": 2,
            "reuse_sources": 0,
        }

    result = await run(
        _arguments(repository, tmp_path / "rehearsals", attempt_id="attempt-1"),
        scope_resetter=reset_scope,
        pair_runner=run_pair,
    )

    assert resets == [
        (
            (
                "uv",
                "run",
                "--project",
                str(repository / "registry"),
                "kintsugi-registry-admin",
            ),
            (tmp_path / "rehearsals").resolve(),
            "dst-pair",
        )
    ]
    assert len(pairs) == 1
    assert pairs[0].pair_id == "attempt-1"
    assert pairs[0].skills_dir == (
        tmp_path / "rehearsals" / "dst-pair" / "skills"
    ).resolve()
    assert pairs[0].artifacts_root == (
        tmp_path / "rehearsals" / "dst-pair" / "attempts"
    ).resolve()
    assert result["scope"] == "dst-pair"
    assert result["research_decision"] == "research"
    assert result["reuse_decision"] == "reuse"


@pytest.mark.asyncio
async def test_rehearsal_can_repeat_without_removing_prior_artifacts(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    rehearsals_root = tmp_path / "rehearsals"
    attempts: list[str] = []

    async def reset_scope(
        command: tuple[str, ...], root: Path, scope: str
    ) -> None:
        (root / scope / "skills").mkdir(parents=True, exist_ok=True)

    async def run_pair(arguments: argparse.Namespace) -> dict[str, Any]:
        attempts.append(str(arguments.pair_id))
        artifacts = Path(arguments.artifacts_root) / str(arguments.pair_id)
        artifacts.mkdir(parents=True)
        (artifacts / "proof.json").write_text("{}\n", encoding="utf-8")
        return {
            "pair_id": arguments.pair_id,
            "outcome": "passed",
            "skill_id": "datetime-semantics",
            "research_sources": 1,
            "reuse_sources": 0,
        }

    for attempt_id in ("attempt-1", "attempt-2"):
        await run(
            _arguments(repository, rehearsals_root, attempt_id=attempt_id),
            scope_resetter=reset_scope,
            pair_runner=run_pair,
        )

    assert attempts == ["attempt-1", "attempt-2"]
    assert (
        rehearsals_root / "dst-pair" / "attempts" / "attempt-1" / "proof.json"
    ).is_file()
    assert (
        rehearsals_root / "dst-pair" / "attempts" / "attempt-2" / "proof.json"
    ).is_file()


def _arguments(
    repository: Path, rehearsals_root: Path, *, attempt_id: str
) -> argparse.Namespace:
    return argparse.Namespace(
        repository=repository,
        rehearsals_root=rehearsals_root,
        scope="dst-pair",
        attempt_id=attempt_id,
        registry_command=None,
        registry_admin_command=None,
        max_turns=40,
        max_budget_usd=None,
    )
