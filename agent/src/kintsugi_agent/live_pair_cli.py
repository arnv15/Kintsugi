"""Paid, opt-in live acceptance for the issue #6 Research-to-Reuse pair."""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from .live_pair import LivePairError, validate_live_pair, validate_research_run
from .orchestrator import AgentRuntime, RunSpec
from .paths import require_safe_directory_name

ROOT_CAUSE_CLASS = "DST-boundary datetime arithmetic"
RESEARCH_TEST = (
    "sandbox.tests.test_scheduling.RecurringScheduleTests."
    "test_daily_run_keeps_its_local_appointment_after_spring_forward"
)
REUSE_TEST = (
    "sandbox.tests.test_reports.WorkedTimeReportTests."
    "test_overnight_fallback_shift_counts_the_repeated_hour"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Spend live model tokens to verify a Research Run publishes a Skill "
            "and a fresh paired Run reuses it without WebFetch."
        )
    )
    parser.add_argument(
        "--pair-id",
        default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        help="Safe identifier for a new retained artifact directory.",
    )
    parser.add_argument("--repository", type=Path, default=_repository_root())
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        help="Parent for retained pair artifacts (default: .kintsugi/live-pairs).",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        help="Registry Skill directory (default: the pair's isolated skills directory).",
    )
    parser.add_argument(
        "--registry-command",
        help="Override the Registry stdio command.",
    )
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--max-budget-usd", type=float)
    return parser


async def run(arguments: argparse.Namespace) -> dict[str, Any]:
    pair_id = require_safe_directory_name(
        str(arguments.pair_id),
        field="pair_id",
    )

    repository = Path(arguments.repository).resolve()
    artifacts_root = (
        Path(arguments.artifacts_root).resolve()
        if arguments.artifacts_root is not None
        else repository / ".kintsugi" / "live-pairs"
    )
    artifacts = artifacts_root / pair_id
    if artifacts.exists():
        raise LivePairError(
            f"Live-pair artifacts already exist at '{artifacts}'; choose a new pair id."
        )

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

    events_path = artifacts / "events.jsonl"
    skills_dir = (
        Path(arguments.skills_dir).resolve()
        if arguments.skills_dir is not None
        else artifacts / "skills"
    )
    runtime = AgentRuntime(
        repository=repository,
        events_path=events_path,
        runs_root=artifacts / "runs",
        registry_command=registry_command,
        registry_env=isolated_registry_environment(skills_dir),
    )
    research_run_id = f"{pair_id}-research-scheduling"
    reuse_run_id = f"{pair_id}-reuse-reports"

    research = await runtime.execute(
        _spec(
            run_id=research_run_id,
            bug_id="scheduling",
            test_id=RESEARCH_TEST,
            arguments=arguments,
        )
    )
    if research.outcome != "passed":
        raise LivePairError(
            f"Research Run failed; retained artifacts are at '{artifacts}'."
        )
    parsed_research = _read_events(events_path)
    validate_research_run(parsed_research, research_run_id)

    reuse = await runtime.execute(
        _spec(
            run_id=reuse_run_id,
            bug_id="reports",
            test_id=REUSE_TEST,
            arguments=arguments,
        )
    )
    parsed = _read_events(events_path)
    summary = validate_live_pair(parsed, research_run_id, reuse_run_id)
    return {
        "pair_id": pair_id,
        "outcome": "passed",
        **summary,
        "research_worktree": str(research.worktree),
        "reuse_worktree": str(reuse.worktree),
        "events_path": str(events_path),
        "skills_dir": str(skills_dir),
    }


def _spec(
    run_id: str,
    bug_id: str,
    test_id: str,
    arguments: argparse.Namespace,
) -> RunSpec:
    return RunSpec(
        run_id=run_id,
        bug_id=bug_id,
        root_cause_class=ROOT_CAUSE_CLASS,
        tests_path=Path("sandbox/tests"),
        test_command=("python3", "-m", "unittest", test_id, "-v"),
        max_turns=int(arguments.max_turns),
        max_budget_usd=arguments.max_budget_usd,
    )


def main(argv: Sequence[str] | None = None) -> None:
    arguments = build_parser().parse_args(argv)
    print(json.dumps(asyncio.run(run(arguments)), indent=2))


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_events(events_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]


def isolated_registry_environment(skills_dir: Path) -> dict[str, str]:
    """Configure a local store that ambient shared-Registry settings cannot refill."""
    return {
        "KINTSUGI_SKILLS_DIR": str(skills_dir),
        "KINTSUGI_SKILLS_REMOTE": "",
    }


if __name__ == "__main__":  # pragma: no cover
    main()
