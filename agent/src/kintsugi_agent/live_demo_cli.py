"""Paid, opt-in command for the complete issue #7 six-Run capture."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import shlex
from pathlib import Path
from typing import Any, Sequence

from .live_demo import LiveDemoError, build_demo_specs, validate_live_demo
from .orchestrator import AgentRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Spend live Anthropic API budget on the exact "
            "A1 → A2 → B1 → B2 → C1 → C2 demo capture."
        )
    )
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--repository", type=Path, default=_repository_root())
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument(
        "--registry-command",
        help="Override the Registry stdio command.",
    )
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument(
        "--max-budget-usd",
        type=float,
        required=True,
        help="Required per-Run SDK budget; total configured exposure is six times this.",
    )
    return parser


async def run(arguments: argparse.Namespace) -> dict[str, Any]:
    capture_id = str(arguments.capture_id)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", capture_id):
        raise ValueError("capture_id must be a safe single directory name")
    if arguments.max_budget_usd <= 0:
        raise ValueError("max_budget_usd must be positive")

    repository = Path(arguments.repository).resolve()
    artifact_dir = (
        Path(arguments.artifact_dir).resolve()
        if arguments.artifact_dir
        else repository / "demo" / "issue-7"
    )
    events_path = artifact_dir / "events.jsonl"
    skills_dir = artifact_dir / "skills"
    runs_root = repository / ".kintsugi" / "live-demos" / capture_id / "runs"
    occupied = [
        path for path in (events_path, skills_dir, runs_root) if path.exists()
    ]
    if occupied:
        rendered = ", ".join(str(path) for path in occupied)
        raise LiveDemoError(
            f"Capture outputs already exist ({rendered}); live evidence is never reused."
        )

    registry_command = _registry_command(arguments.registry_command, repository)
    runtime = AgentRuntime(
        repository=repository,
        events_path=events_path,
        runs_root=runs_root,
        registry_command=registry_command,
        registry_env={"KINTSUGI_SKILLS_DIR": str(skills_dir)},
    )
    specs = build_demo_specs(
        capture_id=capture_id,
        max_turns=int(arguments.max_turns),
        max_budget_usd=float(arguments.max_budget_usd),
        model=str(arguments.model),
    )
    outcomes = []
    for spec in specs:
        outcomes.append(await runtime.execute(spec))

    parsed = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    summary = validate_live_demo(parsed, capture_id=capture_id)
    return {
        **summary,
        "model": str(arguments.model),
        "max_turns": int(arguments.max_turns),
        "max_budget_usd_per_run": float(arguments.max_budget_usd),
        "max_configured_budget_usd": 6 * float(arguments.max_budget_usd),
        "events_path": str(events_path),
        "skills_dir": str(skills_dir),
        "worktrees": [str(outcome.worktree) for outcome in outcomes],
    }


def main(argv: Sequence[str] | None = None) -> None:
    arguments = build_parser().parse_args(argv)
    print(json.dumps(asyncio.run(run(arguments)), indent=2))


def _registry_command(
    configured: str | None,
    repository: Path,
) -> tuple[str, ...]:
    if configured:
        command = tuple(shlex.split(configured))
        if not command:
            raise ValueError("registry command must not be empty")
        return command

    executable = repository / "registry" / ".venv" / "bin" / "kintsugi-registry"
    if not executable.is_file():
        raise LiveDemoError(
            f"Registry environment is not synced; expected '{executable}'."
        )
    return (str(executable),)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


if __name__ == "__main__":  # pragma: no cover
    main()
