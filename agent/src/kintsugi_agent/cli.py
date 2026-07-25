"""Command-line entry point for one Kintsugi Run."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
from pathlib import Path
from typing import Sequence

from .orchestrator import AgentRuntime, RunSpec


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Attempt one Seeded Bug in a fresh baseline worktree."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--bug-id", required=True)
    parser.add_argument("--root-cause-class", required=True)
    parser.add_argument(
        "--test-command",
        required=True,
        help="Verification command, parsed without a shell.",
    )
    parser.add_argument("--tests-path", default="sandbox/tests")
    parser.add_argument("--repository", type=Path, default=_repository_root())
    parser.add_argument("--events-path", type=Path)
    parser.add_argument("--runs-root", type=Path)
    parser.add_argument(
        "--registry-command",
        help="Override the Registry stdio command.",
    )
    parser.add_argument("--skills-dir", type=Path)
    parser.add_argument("--skills-remote")
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--max-budget-usd", type=float)
    return parser


async def run(arguments: argparse.Namespace) -> dict[str, str]:
    repository = arguments.repository.resolve()
    registry_command = (
        tuple(shlex.split(arguments.registry_command))
        if arguments.registry_command
        else (
            "uv",
            "run",
            "--project",
            str(repository / "registry"),
            "kintsugi-registry",
        )
    )
    if not registry_command:
        raise ValueError("registry command must not be empty")

    registry_env = _registry_env(arguments)
    runtime = AgentRuntime(
        repository=repository,
        events_path=arguments.events_path or repository / "events.jsonl",
        runs_root=arguments.runs_root,
        registry_command=registry_command,
        registry_env=registry_env,
    )
    outcome = await runtime.execute(
        RunSpec(
            run_id=arguments.run_id,
            bug_id=arguments.bug_id,
            root_cause_class=arguments.root_cause_class,
            tests_path=Path(arguments.tests_path),
            test_command=tuple(shlex.split(arguments.test_command)),
            max_turns=arguments.max_turns,
            max_budget_usd=arguments.max_budget_usd,
        )
    )
    return {
        "run_id": outcome.run_id,
        "outcome": outcome.outcome,
        "worktree": str(outcome.worktree),
        "events_path": str(outcome.events_path),
    }


def main(argv: Sequence[str] | None = None) -> None:
    arguments = build_parser().parse_args(argv)
    print(json.dumps(asyncio.run(run(arguments)), indent=2))


def _registry_env(arguments: argparse.Namespace) -> dict[str, str]:
    environment: dict[str, str] = {}
    skills_dir = arguments.skills_dir or os.environ.get("KINTSUGI_SKILLS_DIR")
    skills_remote = arguments.skills_remote or os.environ.get(
        "KINTSUGI_SKILLS_REMOTE"
    )
    if skills_dir:
        environment["KINTSUGI_SKILLS_DIR"] = str(skills_dir)
    if skills_remote:
        environment["KINTSUGI_SKILLS_REMOTE"] = str(skills_remote)
    return environment


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


if __name__ == "__main__":  # pragma: no cover
    main()
