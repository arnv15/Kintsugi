from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kintsugi_agent.events import EventLog
from kintsugi_agent.runtime_tools import RuntimeTools
from kintsugi_agent.verification import CommandResult, VerificationRunner


class RuntimeToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_retrieved_skill_is_installed_inside_the_run_worktree(self) -> None:
        async def no_process(
            _command: tuple[str, ...], _cwd: Path
        ) -> CommandResult:
            raise AssertionError("verification was not requested")

        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            events = EventLog(worktree / "events.jsonl", "reuse-run")
            await events.append(
                "registry_queried",
                decision="reuse",
                top_score=0.93,
                skill_id="datetime-semantics",
            )
            tools = RuntimeTools(
                worktree=worktree,
                events=events,
                verifier=VerificationRunner(
                    worktree=worktree,
                    tests_path=Path("sandbox/tests"),
                    test_command=("python3", "-m", "unittest"),
                    command_runner=no_process,
                ),
            )

            result = await tools.install_skill(
                skill_id="datetime-semantics",
                name="Datetime semantics",
                document="---\nname: Datetime semantics\n---\n\nUse the documented semantics.",
            )

            installed = (
                worktree
                / ".claude"
                / "skills"
                / "datetime-semantics"
                / "SKILL.md"
            )
            self.assertEqual(
                "---\nname: Datetime semantics\n---\n\nUse the documented semantics.",
                installed.read_text(encoding="utf-8"),
            )
            self.assertTrue(result["installed"])

    async def test_strategy_requires_a_hypothesis_and_primary_source(self) -> None:
        async def no_process(
            _command: tuple[str, ...], _cwd: Path
        ) -> CommandResult:
            raise AssertionError("verification was not requested")

        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            events = EventLog(worktree / "events.jsonl", "research-run")
            tools = RuntimeTools(
                worktree=worktree,
                events=events,
                verifier=VerificationRunner(
                    worktree=worktree,
                    tests_path=Path("sandbox/tests"),
                    test_command=("python3", "-m", "unittest"),
                    command_runner=no_process,
                ),
            )

            without_hypothesis = await tools.record_strategy(
                strategy="Change the implementation.",
                sources=["https://docs.python.org/"],
            )
            await events.append("hypothesis_formed", text="A diagnosed cause.")
            without_source = await tools.record_strategy(
                strategy="Change the implementation.",
                sources=[],
            )

        self.assertFalse(without_hypothesis["recorded"])
        self.assertFalse(without_source["recorded"])


if __name__ == "__main__":
    unittest.main()
