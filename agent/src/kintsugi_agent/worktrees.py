"""Fresh detached worktree creation for isolated Runs."""

from __future__ import annotations

import re
from pathlib import Path

from .verification import CommandRunner, run_command


class WorktreeError(RuntimeError):
    """A fresh Run worktree could not be created."""


class WorktreeManager:
    """Create one inspectable worktree per Run from an immutable tag."""

    def __init__(
        self,
        repository: Path,
        runs_root: Path,
        baseline: str = "baseline",
        command_runner: CommandRunner | None = None,
    ) -> None:
        self.repository = Path(repository).resolve()
        self.runs_root = Path(runs_root).resolve()
        self.baseline = baseline
        self.command_runner = command_runner or run_command

    async def create(self, run_id: str) -> Path:
        """Create a new detached worktree and refuse to reuse any existing path."""
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", run_id):
            raise ValueError("run_id must be a safe single directory name")

        target = self.runs_root / run_id
        if target.exists():
            raise WorktreeError(
                f"Run worktree '{target}' already exists; Run worktrees are never reused."
            )
        target.parent.mkdir(parents=True, exist_ok=True)

        command = (
            "git",
            "worktree",
            "add",
            "--detach",
            str(target),
            self.baseline,
        )
        result = await self.command_runner(command, self.repository)
        if result.returncode != 0:
            raise WorktreeError(
                f"Could not create Run worktree from {self.baseline}: {result.output.strip()}"
            )
        return target
