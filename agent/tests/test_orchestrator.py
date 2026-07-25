from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from claude_agent_sdk import ResultMessage

from kintsugi_agent.orchestrator import AgentRuntime, RunSpec


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_creates_worktree_executes_sdk_and_finishes_event_stream(
        self,
    ) -> None:
        prompts: list[str] = []

        class FakeWorktrees:
            def __init__(self, worktree: Path) -> None:
                self.worktree = worktree
                self.run_ids: list[str] = []

            async def create(self, run_id: str) -> Path:
                self.run_ids.append(run_id)
                self.worktree.mkdir()
                return self.worktree

        def capture_runtime_tools(**kwargs: Any) -> object:
            return kwargs["runtime_tools"]

        async def pass_run(options: Any, prompt: str) -> ResultMessage:
            prompts.append(prompt)
            await options.events.append(
                "tests_run",
                passed=1,
                failed=0,
                output_tail="Ran 1 test\nOK",
            )
            return ResultMessage(
                subtype="success",
                duration_ms=1000,
                duration_api_ms=800,
                is_error=False,
                num_turns=3,
                session_id="session-1",
                total_cost_usd=0.03,
                usage={"input_tokens": 80, "output_tokens": 20},
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            events_path = root / "events.jsonl"
            worktrees = FakeWorktrees(root / "run-worktree")
            runtime = AgentRuntime(
                repository=root,
                events_path=events_path,
                worktree_manager=worktrees,
                registry_command=("registry",),
                options_builder=capture_runtime_tools,
                sdk_loop=pass_run,
                clock=lambda: 10.0,
            )

            outcome = await runtime.execute(
                RunSpec(
                    run_id="run-1",
                    bug_id="scheduling",
                    root_cause_class="DST-boundary datetime arithmetic",
                    tests_path=Path("sandbox/tests"),
                    test_command=(
                        "python3",
                        "-m",
                        "unittest",
                        "sandbox.tests.test_scheduling",
                    ),
                )
            )

            events = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(["run-1"], worktrees.run_ids)
        self.assertEqual("passed", outcome.outcome)
        self.assertIn("scheduling", prompts[0])
        self.assertEqual(
            ["run_started", "tests_run", "run_finished"],
            [event["type"] for event in events],
        )


if __name__ == "__main__":
    unittest.main()
