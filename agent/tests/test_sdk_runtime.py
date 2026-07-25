from __future__ import annotations

import importlib.metadata
import tempfile
import unittest
from pathlib import Path

from claude_agent_sdk import ResultMessage

from kintsugi_agent.events import EventLog
from kintsugi_agent.hooks import RunHooks
from kintsugi_agent.runner import (
    SDK_VERSION,
    build_agent_options,
    finish_run,
    run_sdk_loop,
)
from kintsugi_agent.runtime_tools import RuntimeTools
from kintsugi_agent.verification import CommandResult, VerificationRunner


class SDKRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_agent_options_pin_sdk_hooks_web_tools_registry_and_worktree(
        self,
    ) -> None:
        async def no_process(
            _command: tuple[str, ...], _cwd: Path
        ) -> CommandResult:
            raise AssertionError("verification was not requested")

        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory)
            events = EventLog(worktree / "events.jsonl", "run-1")
            hooks = RunHooks(worktree, events)
            runtime_tools = RuntimeTools(
                worktree,
                events,
                VerificationRunner(
                    worktree=worktree,
                    tests_path=Path("sandbox/tests"),
                    test_command=("python3", "-m", "unittest"),
                    command_runner=no_process,
                ),
            )

            options = build_agent_options(
                worktree=worktree,
                hooks=hooks,
                runtime_tools=runtime_tools,
                registry_command=("uv", "run", "--project", "/repo/registry"),
                max_turns=40,
            )

        self.assertEqual(SDK_VERSION, importlib.metadata.version("claude-agent-sdk"))
        self.assertEqual(worktree, options.cwd)
        self.assertTrue(options.strict_mcp_config)
        self.assertEqual({"PreToolUse", "PostToolUse"}, set(options.hooks or {}))
        self.assertTrue({"WebSearch", "WebFetch"}.issubset(set(options.tools or [])))
        self.assertIsInstance(options.mcp_servers, dict)
        assert isinstance(options.mcp_servers, dict)
        self.assertEqual({"skill-registry", "runtime"}, set(options.mcp_servers))
        self.assertEqual("bypassPermissions", options.permission_mode)

    async def test_sdk_loop_returns_the_final_result_message(self) -> None:
        expected = ResultMessage(
            subtype="success",
            duration_ms=1200,
            duration_api_ms=900,
            is_error=False,
            num_turns=3,
            session_id="session-1",
            total_cost_usd=0.04,
            usage={"input_tokens": 100, "output_tokens": 25},
        )

        class FakeClient:
            def __init__(self, options: object) -> None:
                self.options = options
                self.prompt = ""

            async def __aenter__(self) -> "FakeClient":
                return self

            async def __aexit__(self, *_args: object) -> None:
                return None

            async def query(self, prompt: str) -> None:
                self.prompt = prompt

            async def receive_response(self):  # type: ignore[no-untyped-def]
                yield expected

        result = await run_sdk_loop(
            options=object(),
            prompt="Attempt the Seeded Bug.",
            client_factory=FakeClient,
        )

        self.assertIs(expected, result)

    async def test_finish_event_uses_sdk_metrics_and_recorded_run_facts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            events = EventLog(Path(directory) / "events.jsonl", "run-1")
            await events.append(
                "source_read",
                url="https://docs.python.org/",
                title="Python documentation",
            )
            await events.append(
                "tests_run",
                passed=1,
                failed=0,
                output_tail="Ran 1 test\nOK",
            )
            result = ResultMessage(
                subtype="success",
                duration_ms=1200,
                duration_api_ms=900,
                is_error=False,
                num_turns=3,
                session_id="session-1",
                total_cost_usd=0.04,
                usage={"input_tokens": 100, "output_tokens": 25},
            )

            event = await finish_run(events, result=result, seconds=2.5)

        self.assertEqual(
            {
                "outcome": "passed",
                "tokens": 125,
                "cost_usd": 0.04,
                "seconds": 2.5,
                "sources_count": 1,
            },
            {
                field: event[field]
                for field in (
                    "outcome",
                    "tokens",
                    "cost_usd",
                    "seconds",
                    "sources_count",
                )
            },
        )

    async def test_finish_marks_post_verification_edits_failed_and_keeps_unknown_metrics(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            events = EventLog(Path(directory) / "events.jsonl", "run-1")
            await events.append(
                "tests_run",
                passed=1,
                failed=0,
                output_tail="Ran 1 test\nOK",
            )
            await events.append(
                "patch_applied",
                files_touched=["sandbox/bug.py"],
            )
            result = ResultMessage(
                subtype="success",
                duration_ms=1200,
                duration_api_ms=900,
                is_error=False,
                num_turns=3,
                session_id="session-1",
                total_cost_usd=None,
                usage=None,
            )

            event = await finish_run(events, result=result, seconds=2.5)

        self.assertEqual("failed", event["outcome"])
        self.assertIsNone(event["tokens"])
        self.assertIsNone(event["cost_usd"])


if __name__ == "__main__":
    unittest.main()
