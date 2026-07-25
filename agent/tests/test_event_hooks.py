from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kintsugi_agent.events import EventLog, validate_event
from kintsugi_agent.hooks import RunHooks


class PostToolEventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.worktree = Path(self.temporary_directory.name)
        (self.worktree / "sandbox").mkdir()
        self.events_path = self.worktree / "events.jsonl"
        self.events = EventLog(self.events_path, "research-run")
        self.hooks = RunHooks(self.worktree, self.events)

    async def post(
        self,
        tool_name: str,
        tool_input: dict[str, object],
        tool_response: object,
    ) -> None:
        await self.hooks.post_tool_use(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_response": tool_response,
            },
            None,
            {"signal": None},
        )

    async def test_research_run_produces_schema_valid_append_only_jsonl(self) -> None:
        await self.events.append(
            "run_started",
            bug_id="scheduling",
            root_cause_class="DST-boundary datetime arithmetic",
        )
        await self.post(
            "mcp__kintsugi-runtime__record_hypothesis",
            {"hypothesis": "Aware datetime arithmetic used the wrong time semantics."},
            {"recorded": True},
        )
        await self.post(
            "mcp__kintsugi-skill-registry__search_skills",
            {"hypothesis": "Aware datetime arithmetic used the wrong time semantics."},
            {"decision": "research", "matches": []},
        )
        await self.post(
            "WebFetch",
            {"url": "https://docs.python.org/3/library/datetime.html"},
            {"title": "datetime — Basic date and time types"},
        )
        await self.post(
            "mcp__kintsugi-runtime__record_strategy",
            {
                "strategy": "Use wall-clock arithmetic for a recurring appointment.",
                "sources": ["https://docs.python.org/3/library/datetime.html"],
            },
            {"recorded": True},
        )
        await self.post(
            "Edit",
            {"file_path": str(self.worktree / "sandbox" / "scheduling.py")},
            {"filePath": str(self.worktree / "sandbox" / "scheduling.py")},
        )
        await self.post(
            "mcp__kintsugi-runtime__verify_fix",
            {},
            {
                "attempt": 1,
                "passed": True,
                "passed_count": 1,
                "failed_count": 0,
                "output_tail": "Ran 1 test\nOK",
            },
        )
        await self.post(
            "mcp__kintsugi-skill-registry__publish_skill",
            {"name": "DST-boundary datetime arithmetic"},
            {
                "published": True,
                "skill_id": "dst-boundary-datetime-arithmetic",
            },
        )
        await self.events.append(
            "run_finished",
            outcome="passed",
            tokens=1234,
            cost_usd=0.12,
            seconds=42,
            sources_count=1,
        )

        lines = self.events_path.read_text(encoding="utf-8").splitlines()
        parsed = [json.loads(line) for line in lines]
        for event in parsed:
            validate_event(event)

        self.assertEqual(
            [
                "run_started",
                "hypothesis_formed",
                "registry_queried",
                "source_read",
                "strategy_recorded",
                "patch_applied",
                "tests_run",
                "skill_published",
                "run_finished",
            ],
            [event["type"] for event in parsed],
        )
        self.assertEqual(list(range(1, 10)), [event["seq"] for event in parsed])

    async def test_reuse_decision_denies_web_fetch(self) -> None:
        await self.events.append(
            "registry_queried",
            decision="reuse",
            top_score=0.92,
            skill_id="known-skill",
        )

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

    async def test_rejected_logging_tool_does_not_create_run_state(self) -> None:
        await self.post(
            "mcp__kintsugi-runtime__record_strategy",
            {"strategy": "Uncited fix.", "sources": []},
            {"recorded": False, "feedback": "A primary source is required."},
        )

        self.assertEqual([], await self.events.events())

    async def test_reuse_event_follows_the_inherited_cited_strategy(self) -> None:
        await self.events.append(
            "registry_queried",
            decision="reuse",
            top_score=0.92,
            skill_id="known-skill",
        )
        await self.post(
            "mcp__kintsugi-runtime__install_skill",
            {
                "skill_id": "known-skill",
                "name": "Known Skill",
                "document": "---\nname: Known Skill\n---\n",
            },
            {"installed": True},
        )
        await self.post(
            "mcp__kintsugi-runtime__record_strategy",
            {
                "strategy": "Apply the inherited strategy.",
                "sources": ["https://example.test/primary"],
            },
            {
                "recorded": True,
                "reused_skill": {"id": "known-skill", "name": "Known Skill"},
            },
        )

        self.assertEqual(
            ["registry_queried", "strategy_recorded", "skill_reused"],
            [event["type"] for event in await self.events.events()],
        )

    async def test_get_skill_hook_retains_the_authoritative_install_payload(
        self,
    ) -> None:
        payload = {
            "id": "known-skill",
            "name": "Known Skill",
            "document": "---\nname: Known Skill\n---\n\nApply the strategy.",
            "sources": ["https://example.test/primary"],
        }

        await self.post(
            "mcp__kintsugi-skill-registry__get_skill",
            {"skill_id": "known-skill"},
            {"content": [{"type": "text", "text": json.dumps(payload)}]},
        )

        self.assertEqual(payload, await self.events.retrieved_skill("known-skill"))

    async def test_second_failed_verification_stops_the_sdk_loop(self) -> None:
        first = await self.hooks.post_tool_use(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "mcp__kintsugi-runtime__verify_fix",
                "tool_input": {},
                "tool_response": {
                    "attempt": 1,
                    "passed": False,
                    "passed_count": 0,
                    "failed_count": 1,
                    "output_tail": "FAILED",
                },
            },
            None,
            {"signal": None},
        )
        second = await self.hooks.post_tool_use(
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "mcp__kintsugi-runtime__verify_fix",
                "tool_input": {},
                "tool_response": {
                    "attempt": 2,
                    "passed": False,
                    "passed_count": 0,
                    "failed_count": 1,
                    "output_tail": "FAILED",
                },
            },
            None,
            {"signal": None},
        )

        self.assertNotIn("continue_", first)
        self.assertFalse(second["continue_"])


if __name__ == "__main__":
    unittest.main()
