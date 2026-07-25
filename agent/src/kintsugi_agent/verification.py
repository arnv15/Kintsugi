"""Mechanically restore committed tests and enforce the two-attempt limit."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    """The process facts needed by verification."""

    returncode: int
    output: str


CommandRunner = Callable[[tuple[str, ...], Path], Awaitable[CommandResult]]


class VerificationError(RuntimeError):
    """Committed tests could not be restored before verification."""


class VerificationRunner:
    """The only supported verification path for one Run."""

    def __init__(
        self,
        worktree: Path,
        tests_path: Path,
        test_command: tuple[str, ...],
        command_runner: CommandRunner | None = None,
        max_attempts: int = 2,
    ) -> None:
        self.worktree = Path(worktree)
        self.tests_path = Path(tests_path)
        if self.tests_path.is_absolute() or ".." in self.tests_path.parts:
            raise ValueError("tests_path must stay within the Run worktree")
        if not test_command:
            raise ValueError("test_command must not be empty")
        self.test_command = test_command
        self.command_runner = command_runner or run_command
        self.max_attempts = max_attempts
        self.attempts = 0

    async def verify(self) -> dict[str, Any]:
        """Restore tests, run verification, and return observable test facts."""
        if self.attempts >= self.max_attempts:
            return {
                "attempted": False,
                "attempt": None,
                "passed": False,
                "passed_count": 0,
                "failed_count": 0,
                "output_tail": (
                    f"Verification refused: this Run already used {self.max_attempts} attempts."
                ),
            }

        self.attempts += 1
        restore_command = ("git", "checkout", "--", self.tests_path.as_posix())
        restore = await self.command_runner(restore_command, self.worktree)
        if restore.returncode != 0:
            raise VerificationError(
                "Could not restore committed tests before verification: "
                f"{restore.output.strip()}"
            )

        # This call intentionally follows the restore with no intervening work.
        test_result = await self.command_runner(self.test_command, self.worktree)
        passed_count, failed_count = _test_counts(
            test_result.output, test_result.returncode
        )
        return {
            "attempted": True,
            "attempt": self.attempts,
            "passed": test_result.returncode == 0,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "output_tail": test_result.output[-2000:],
        }


async def run_command(command: tuple[str, ...], cwd: Path) -> CommandResult:
    """Run one command without a shell and combine its stdout and stderr."""
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    return CommandResult(
        returncode=process.returncode or 0,
        output=stdout.decode("utf-8", errors="replace"),
    )


def _test_counts(output: str, returncode: int) -> tuple[int, int]:
    match = re.search(r"Ran\s+(\d+)\s+tests?", output)
    total = int(match.group(1)) if match else 1
    if returncode == 0:
        return total, 0

    failures = sum(
        int(value)
        for value in re.findall(r"(?:failures|errors)=(\d+)", output)
    )
    failed = failures or 1
    return max(0, total - failed), failed
