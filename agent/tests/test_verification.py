from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kintsugi_agent.verification import CommandResult, VerificationRunner


class VerificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_tests_are_restored_immediately_before_verification(self) -> None:
        calls: list[tuple[tuple[str, ...], Path]] = []

        async def run(command: tuple[str, ...], cwd: Path) -> CommandResult:
            calls.append((command, cwd))
            return CommandResult(returncode=0, output="Ran 1 test\nOK")

        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            verifier = VerificationRunner(
                worktree=worktree,
                tests_path=Path("sandbox/tests"),
                test_command=("python3", "-m", "unittest", "sandbox.tests.test_scheduling"),
                command_runner=run,
            )

            result = await verifier.verify()

        self.assertEqual(
            [
                (("git", "checkout", "--", "sandbox/tests"), worktree),
                (
                    (
                        "python3",
                        "-m",
                        "unittest",
                        "sandbox.tests.test_scheduling",
                    ),
                    worktree,
                ),
            ],
            calls,
        )
        self.assertTrue(result["passed"])

    async def test_third_attempt_is_refused_without_running_commands(self) -> None:
        calls: list[tuple[str, ...]] = []

        async def fail(command: tuple[str, ...], _cwd: Path) -> CommandResult:
            calls.append(command)
            if command[0] == "git":
                return CommandResult(returncode=0, output="")
            return CommandResult(returncode=1, output="Ran 1 test\nFAILED")

        with tempfile.TemporaryDirectory() as directory:
            verifier = VerificationRunner(
                worktree=Path(directory),
                tests_path=Path("sandbox/tests"),
                test_command=("python3", "-m", "unittest", "sandbox.tests.test_scheduling"),
                command_runner=fail,
            )

            first = await verifier.verify()
            second = await verifier.verify()
            third = await verifier.verify()

        self.assertEqual([1, 2, None], [first["attempt"], second["attempt"], third["attempt"]])
        self.assertEqual(4, len(calls))
        self.assertFalse(third["attempted"])


if __name__ == "__main__":
    unittest.main()
