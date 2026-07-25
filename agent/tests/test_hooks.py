from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kintsugi_agent.events import EventLog
from kintsugi_agent.hooks import RunHooks


class EditPolicyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.worktree = Path(self.temporary_directory.name)
        (self.worktree / "sandbox" / "tests").mkdir(parents=True)
        (self.worktree / "sandbox").mkdir(exist_ok=True)
        self.test_file = self.worktree / "sandbox" / "tests" / "test_bug.py"
        self.test_file.write_text("original\n", encoding="utf-8")
        self.source_file = self.worktree / "sandbox" / "bug.py"
        self.source_file.write_text("broken = True\n", encoding="utf-8")
        self.events = EventLog(
            path=self.worktree / "events.jsonl",
            run_id="run-1",
        )
        self.hooks = RunHooks(worktree=self.worktree, events=self.events)

    async def test_edit_under_tests_is_denied_without_modifying_the_file(self) -> None:
        decision = await self.hooks.pre_tool_use(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": str(self.test_file)},
            },
            None,
            {"signal": None},
        )

        self.assertEqual("original\n", self.test_file.read_text(encoding="utf-8"))
        self.assertEqual(
            "deny",
            decision["hookSpecificOutput"]["permissionDecision"],
        )

    async def test_source_edit_before_hypothesis_and_strategy_is_denied(self) -> None:
        decision = await self.hooks.pre_tool_use(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Write",
                "tool_input": {"file_path": str(self.source_file)},
            },
            None,
            {"signal": None},
        )

        self.assertEqual(
            "deny",
            decision["hookSpecificOutput"]["permissionDecision"],
        )

    async def test_source_edit_after_hypothesis_and_strategy_is_allowed(self) -> None:
        await self.events.append("hypothesis_formed", text="A diagnosed cause.")
        await self.events.append(
            "strategy_recorded",
            text="Apply the cited correction.",
            sources=["https://example.test/primary-source"],
        )

        decision = await self.hooks.pre_tool_use(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Edit",
                "tool_input": {"file_path": str(self.source_file)},
            },
            None,
            {"signal": None},
        )

        self.assertEqual(
            "allow",
            decision["hookSpecificOutput"]["permissionDecision"],
        )

    async def test_skill_publish_is_allowed_only_after_green_research_tests(self) -> None:
        await self.events.append(
            "registry_queried",
            decision="research",
            top_score=0.0,
            skill_id=None,
        )
        before_tests = await self.hooks.pre_tool_use(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "mcp__kintsugi-skill-registry__publish_skill",
                "tool_input": {"name": "A Root Cause Class"},
            },
            None,
            {"signal": None},
        )
        await self.events.append(
            "tests_run",
            passed=1,
            failed=0,
            output_tail="Ran 1 test\nOK",
        )
        after_tests = await self.hooks.pre_tool_use(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "mcp__kintsugi-skill-registry__publish_skill",
                "tool_input": {"name": "A Root Cause Class"},
            },
            None,
            {"signal": None},
        )

        self.assertEqual(
            ["deny", "allow"],
            [
                before_tests["hookSpecificOutput"]["permissionDecision"],
                after_tests["hookSpecificOutput"]["permissionDecision"],
            ],
        )

    async def test_edit_after_green_invalidates_permission_to_publish(self) -> None:
        await self.events.append(
            "registry_queried",
            decision="research",
            top_score=0.0,
            skill_id=None,
        )
        await self.events.append(
            "tests_run",
            passed=1,
            failed=0,
            output_tail="Ran 1 test\nOK",
        )
        await self.events.append(
            "patch_applied",
            files_touched=["sandbox/bug.py"],
        )

        decision = await self.hooks.pre_tool_use(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "mcp__kintsugi-skill-registry__publish_skill",
                "tool_input": {"name": "A Root Cause Class"},
            },
            None,
            {"signal": None},
        )

        self.assertEqual(
            "deny",
            decision["hookSpecificOutput"]["permissionDecision"],
        )

    async def test_web_fetch_requires_an_explicit_research_decision(self) -> None:
        decision = await self.hooks.pre_tool_use(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://example.test/source"},
            },
            None,
            {"signal": None},
        )

        self.assertEqual(
            "deny",
            decision["hookSpecificOutput"]["permissionDecision"],
        )

    async def test_direct_bash_verification_is_denied(self) -> None:
        decision = await self.hooks.pre_tool_use(
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "python3 -m unittest sandbox.tests.test_scheduling -v"
                },
            },
            None,
            {"signal": None},
        )

        self.assertEqual(
            "deny",
            decision["hookSpecificOutput"]["permissionDecision"],
        )


if __name__ == "__main__":
    unittest.main()
