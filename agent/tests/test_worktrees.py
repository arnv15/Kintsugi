from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kintsugi_agent.verification import CommandResult
from kintsugi_agent.worktrees import WorktreeManager


class WorktreeTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_run_gets_a_fresh_detached_worktree_from_baseline(self) -> None:
        calls: list[tuple[tuple[str, ...], Path]] = []

        async def add_worktree(
            command: tuple[str, ...], cwd: Path
        ) -> CommandResult:
            calls.append((command, cwd))
            Path(command[-2]).mkdir(parents=True)
            return CommandResult(returncode=0, output="Preparing worktree")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repository = root / "repo"
            repository.mkdir()
            manager = WorktreeManager(
                repository=repository,
                runs_root=root / "runs",
                command_runner=add_worktree,
            )

            first = await manager.create("run-one")
            second = await manager.create("run-two")

        self.assertNotEqual(first, second)
        self.assertEqual(
            [
                (
                    (
                        "git",
                        "worktree",
                        "add",
                        "--detach",
                        str(root / "runs" / "run-one"),
                        "baseline",
                    ),
                    repository,
                ),
                (
                    (
                        "git",
                        "worktree",
                        "add",
                        "--detach",
                        str(root / "runs" / "run-two"),
                        "baseline",
                    ),
                    repository,
                ),
            ],
            calls,
        )


if __name__ == "__main__":
    unittest.main()
