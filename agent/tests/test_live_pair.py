from __future__ import annotations

import unittest

from kintsugi_agent.live_pair import LivePairError, validate_live_pair


class LivePairValidationTests(unittest.TestCase):
    def test_accepts_research_then_reuse_without_second_run_sources(self) -> None:
        events = [
            {
                "run_id": "research",
                "type": "registry_queried",
                "decision": "research",
            },
            {"run_id": "research", "type": "source_read"},
            {
                "run_id": "research",
                "type": "skill_published",
                "skill_id": "datetime-semantics",
            },
            {
                "run_id": "research",
                "type": "run_finished",
                "outcome": "passed",
            },
            {
                "run_id": "reuse",
                "type": "registry_queried",
                "decision": "reuse",
            },
            {
                "run_id": "reuse",
                "type": "skill_reused",
                "skill_id": "datetime-semantics",
            },
            {
                "run_id": "reuse",
                "type": "run_finished",
                "outcome": "passed",
            },
        ]

        summary = validate_live_pair(events, "research", "reuse")

        self.assertEqual("datetime-semantics", summary["skill_id"])
        self.assertEqual(1, summary["research_sources"])
        self.assertEqual(0, summary["reuse_sources"])

    def test_rejects_web_fetch_observed_during_reuse(self) -> None:
        events = [
            {
                "run_id": "research",
                "type": "registry_queried",
                "decision": "research",
            },
            {"run_id": "research", "type": "source_read"},
            {
                "run_id": "research",
                "type": "skill_published",
                "skill_id": "datetime-semantics",
            },
            {
                "run_id": "research",
                "type": "run_finished",
                "outcome": "passed",
            },
            {
                "run_id": "reuse",
                "type": "registry_queried",
                "decision": "reuse",
            },
            {"run_id": "reuse", "type": "source_read"},
            {
                "run_id": "reuse",
                "type": "skill_reused",
                "skill_id": "datetime-semantics",
            },
            {
                "run_id": "reuse",
                "type": "run_finished",
                "outcome": "passed",
            },
        ]

        with self.assertRaisesRegex(LivePairError, "zero source_read"):
            validate_live_pair(events, "research", "reuse")


if __name__ == "__main__":
    unittest.main()
