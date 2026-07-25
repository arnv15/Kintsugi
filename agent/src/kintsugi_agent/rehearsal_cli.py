"""Repeatable cold-to-warm rehearsal for the first paired Seeded Bugs."""

from __future__ import annotations

import argparse
import asyncio
import json
import shlex
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .live_pair_cli import run as run_live_pair
from .paths import require_safe_directory_name

ScopeResetter = Callable[[tuple[str, ...], Path, str], Awaitable[None]]
PairRunner = Callable[[argparse.Namespace], Awaitable[dict[str, Any]]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Reset an isolated Registry scope, prove scheduling takes the Research "
            "Path, then prove reports takes the Reuse Path."
        )
    )
    parser.add_argument("--repository", type=Path, default=_repository_root())
    parser.add_argument(
        "--rehearsals-root",
        type=Path,
        help="Root for retained rehearsal scopes (default: .kintsugi/rehearsals).",
    )
    parser.add_argument("--scope", default="dst-cold-warm")
    parser.add_argument(
        "--attempt-id",
        default=None,
        help="Safe retained-attempt name (default: unique UTC timestamp).",
    )
    parser.add_argument("--registry-command", help="Override the Registry MCP command.")
    parser.add_argument(
        "--registry-admin-command",
        help="Override the Registry operator command used to reset the scope.",
    )
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--max-budget-usd", type=float)
    return parser


async def run(
    arguments: argparse.Namespace,
    *,
    scope_resetter: ScopeResetter | None = None,
    pair_runner: PairRunner = run_live_pair,
) -> dict[str, Any]:
    repository = Path(arguments.repository).resolve()
    rehearsals_root = (
        Path(arguments.rehearsals_root).resolve()
        if arguments.rehearsals_root is not None
        else repository / ".kintsugi" / "rehearsals"
    )
    scope = require_safe_directory_name(str(arguments.scope), field="scope")
    attempt_id = require_safe_directory_name(
        str(arguments.attempt_id or _new_attempt_id()),
        field="attempt_id",
    )
    scope_root = rehearsals_root / scope
    skills_dir = scope_root / "skills"
    artifacts_root = scope_root / "attempts"

    admin_command = _command(
        arguments.registry_admin_command,
        default=(
            "uv",
            "run",
            "--project",
            str(repository / "registry"),
            "kintsugi-registry-admin",
        ),
        field="registry admin command",
    )
    resetter = scope_resetter or _reset_scope
    await resetter(admin_command, rehearsals_root, scope)

    pair_arguments = argparse.Namespace(
        pair_id=attempt_id,
        repository=repository,
        artifacts_root=artifacts_root,
        skills_dir=skills_dir,
        registry_command=arguments.registry_command,
        max_turns=arguments.max_turns,
        max_budget_usd=arguments.max_budget_usd,
    )
    summary = await pair_runner(pair_arguments)
    return {
        "scope": scope,
        "attempt_id": attempt_id,
        "research_decision": "research",
        "reuse_decision": "reuse",
        **summary,
    }


async def _reset_scope(
    admin_command: tuple[str, ...],
    rehearsals_root: Path,
    scope: str,
) -> None:
    process = await asyncio.create_subprocess_exec(
        *admin_command,
        "scope",
        scope,
        "--rehearsals-root",
        str(rehearsals_root),
        "--reset",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        detail = stderr.decode().strip() or stdout.decode().strip()
        raise RuntimeError(f"Registry scope reset failed: {detail}")


def _command(
    override: str | None,
    *,
    default: tuple[str, ...],
    field: str,
) -> tuple[str, ...]:
    command = tuple(shlex.split(override)) if override else default
    if not command:
        raise ValueError(f"{field} must not be empty")
    return command


def _new_attempt_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid4().hex[:8]}"


def main(argv: Sequence[str] | None = None) -> None:
    arguments = build_parser().parse_args(argv)
    print(json.dumps(asyncio.run(run(arguments)), indent=2))


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


if __name__ == "__main__":  # pragma: no cover
    main()
