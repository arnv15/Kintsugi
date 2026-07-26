from __future__ import annotations

import unittest

from kintsugi_agent.live_pair import (
    LivePairError,
    validate_live_pair,
    validate_research_run,
)
from kintsugi_agent.live_pair_cli import (
    RESEARCH_TEST,
    REUSE_TEST,
    _spec,
)
from kintsugi_agent.live_pair_cli import build_parser as build_pair_parser


class LivePairValidationTests(unittest.TestCase):
    def test_research_proof_rejects_a_contaminated_first_run(self) -> None:
        events = [
            {
                "run_id": "research",
                "type": "registry_queried",
                "decision": "reuse",
            },
            {
                "run_id": "research",
                "type": "run_finished",
                "outcome": "passed",
            },
        ]

        with self.assertRaisesRegex(LivePairError, "decision 'research'"):
            validate_research_run(events, "research")

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


class LivePairCliTests(unittest.TestCase):
    def test_rehearsal_pins_the_same_default_model_as_the_paid_capture(self) -> None:
        arguments = build_pair_parser().parse_args([])

        self.assertEqual("claude-sonnet-4-6", arguments.model)

    def test_operator_can_rehearse_against_an_explicit_model(self) -> None:
        arguments = build_pair_parser().parse_args(["--model", "claude-sonnet-5"])

        self.assertEqual("claude-sonnet-5", arguments.model)

    def test_both_rehearsal_runs_carry_the_selected_model(self) -> None:
        arguments = build_pair_parser().parse_args(
            ["--model", "claude-sonnet-4-6", "--max-budget-usd", "2.00"]
        )

        research = _spec(
            run_id="rehearsal-research-scheduling",
            bug_id="scheduling",
            test_id=RESEARCH_TEST,
            arguments=arguments,
        )
        reuse = _spec(
            run_id="rehearsal-reuse-reports",
            bug_id="reports",
            test_id=REUSE_TEST,
            arguments=arguments,
        )

        self.assertEqual("claude-sonnet-4-6", research.model)
        self.assertEqual("claude-sonnet-4-6", reuse.model)


if __name__ == "__main__":
    unittest.main()
