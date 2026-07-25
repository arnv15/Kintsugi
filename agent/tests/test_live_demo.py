from __future__ import annotations

import unittest

from kintsugi_agent.live_demo import (
    LiveDemoError,
    build_demo_specs,
    validate_live_demo,
)
from kintsugi_agent.live_demo_cli import build_parser


class LiveDemoPlanTests(unittest.TestCase):
    def test_cli_requires_the_operator_to_acknowledge_a_cost_budget(self) -> None:
        parser = build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(["--capture-id", "issue-7"])

        arguments = parser.parse_args(
            [
                "--capture-id",
                "issue-7",
                "--max-budget-usd",
                "2.00",
            ]
        )
        self.assertEqual("claude-sonnet-4-6", arguments.model)
        self.assertEqual(2.0, arguments.max_budget_usd)

    def test_builds_the_exact_six_run_demo_order(self) -> None:
        specs = build_demo_specs(
            capture_id="issue-7",
            max_turns=40,
            max_budget_usd=2.0,
            model="claude-sonnet-4-6",
        )

        self.assertEqual(
            [
                "issue-7-A1-scheduling",
                "issue-7-A2-reports",
                "issue-7-B1-checkout",
                "issue-7-B2-payouts",
                "issue-7-C1-fetcher",
                "issue-7-C2-writer",
            ],
            [spec.run_id for spec in specs],
        )
        self.assertEqual(
            [
                "scheduling",
                "reports",
                "checkout",
                "payouts",
                "fetcher",
                "writer",
            ],
            [spec.bug_id for spec in specs],
        )
        self.assertTrue(all(spec.max_turns == 40 for spec in specs))
        self.assertTrue(all(spec.max_budget_usd == 2.0 for spec in specs))
        self.assertTrue(all(spec.model == "claude-sonnet-4-6" for spec in specs))


class LiveDemoValidationTests(unittest.TestCase):
    def test_accepts_three_faster_lower_token_zero_source_reuse_pairs(self) -> None:
        events = _passing_demo_events()

        summary = validate_live_demo(events, capture_id="issue-7")

        self.assertEqual(6, summary["runs_completed"])
        self.assertEqual(3, summary["reuse_pairs"])
        self.assertEqual(
            ["issue-7-A1-scheduling", "issue-7-A2-reports"],
            summary["pairs"][0]["run_ids"],
        )

    def test_rejects_a_reuse_run_that_is_not_strictly_faster(self) -> None:
        events = _passing_demo_events()
        finished = next(
            event
            for event in events
            if event["run_id"] == "issue-7-A2-reports"
            and event["type"] == "run_finished"
        )
        finished["seconds"] = 10.0

        with self.assertRaisesRegex(LiveDemoError, "less wall-clock time"):
            validate_live_demo(events, capture_id="issue-7")

    def test_rejects_any_extra_or_out_of_order_run(self) -> None:
        events = _passing_demo_events()
        first = next(
            index for index, event in enumerate(events) if event["type"] == "run_started"
        )
        second = next(
            index
            for index, event in enumerate(events[first + 1 :], first + 1)
            if event["type"] == "run_started"
        )
        events[first], events[second] = events[second], events[first]

        with self.assertRaisesRegex(LiveDemoError, "exact demo order"):
            validate_live_demo(events, capture_id="issue-7")


def _passing_demo_events() -> list[dict[str, object]]:
    pairs = [
        (
            "A",
            "scheduling",
            "reports",
            "DST-boundary datetime arithmetic",
            "datetime-semantics",
        ),
        (
            "B",
            "checkout",
            "payouts",
            "Money represented as float instead of Decimal",
            "decimal-money",
        ),
        (
            "C",
            "fetcher",
            "writer",
            "asyncio exception semantics",
            "asyncio-semantics",
        ),
    ]
    events: list[dict[str, object]] = []
    for label, first_bug, second_bug, root_cause_class, skill_id in pairs:
        research_id = f"issue-7-{label}1-{first_bug}"
        reuse_id = f"issue-7-{label}2-{second_bug}"
        events.extend(
            [
                {
                    "run_id": research_id,
                    "type": "run_started",
                    "bug_id": first_bug,
                    "root_cause_class": root_cause_class,
                },
                {
                    "run_id": research_id,
                    "type": "registry_queried",
                    "decision": "research",
                },
                {"run_id": research_id, "type": "source_read"},
                {
                    "run_id": research_id,
                    "type": "skill_published",
                    "skill_id": skill_id,
                },
                {
                    "run_id": research_id,
                    "type": "run_finished",
                    "outcome": "passed",
                    "tokens": 1000,
                    "cost_usd": 0.2,
                    "seconds": 10.0,
                    "sources_count": 1,
                },
                {
                    "run_id": reuse_id,
                    "type": "run_started",
                    "bug_id": second_bug,
                    "root_cause_class": root_cause_class,
                },
                {
                    "run_id": reuse_id,
                    "type": "registry_queried",
                    "decision": "reuse",
                },
                {
                    "run_id": reuse_id,
                    "type": "skill_reused",
                    "skill_id": skill_id,
                },
                {
                    "run_id": reuse_id,
                    "type": "run_finished",
                    "outcome": "passed",
                    "tokens": 500,
                    "cost_usd": 0.1,
                    "seconds": 5.0,
                    "sources_count": 0,
                },
            ]
        )
    return events


if __name__ == "__main__":
    unittest.main()
