"""Plan and validate the paid, opt-in six-Run issue #7 capture."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .live_pair import LivePairError, validate_live_pair
from .orchestrator import RunSpec


class LiveDemoError(AssertionError):
    """The six-Run capture did not satisfy issue #7."""


@dataclass(frozen=True)
class DemoBug:
    label: str
    bug_id: str
    root_cause_class: str
    test_id: str


DEMO_BUGS = (
    DemoBug(
        label="A1",
        bug_id="scheduling",
        root_cause_class="DST-boundary datetime arithmetic",
        test_id=(
            "sandbox.tests.test_scheduling.RecurringScheduleTests."
            "test_daily_run_keeps_its_local_appointment_after_spring_forward"
        ),
    ),
    DemoBug(
        label="A2",
        bug_id="reports",
        root_cause_class="DST-boundary datetime arithmetic",
        test_id=(
            "sandbox.tests.test_reports.WorkedTimeReportTests."
            "test_overnight_fallback_shift_counts_the_repeated_hour"
        ),
    ),
    DemoBug(
        label="B1",
        bug_id="checkout",
        root_cause_class="Money represented as float instead of Decimal",
        test_id=(
            "sandbox.tests.test_checkout.CheckoutTotalTests."
            "test_half_cent_tax_rounds_up_on_the_customer_charge"
        ),
    ),
    DemoBug(
        label="B2",
        bug_id="payouts",
        root_cause_class="Money represented as float instead of Decimal",
        test_id=(
            "sandbox.tests.test_payouts.PayoutAllocationTests."
            "test_three_recipient_distribution_preserves_the_entire_fund"
        ),
    ),
    DemoBug(
        label="C1",
        bug_id="fetcher",
        root_cause_class="asyncio exception semantics",
        test_id=(
            "sandbox.tests.test_fetcher.ConcurrentFetchTests."
            "test_batch_request_surfaces_a_failed_dependency"
        ),
    ),
    DemoBug(
        label="C2",
        bug_id="writer",
        root_cause_class="asyncio exception semantics",
        test_id=(
            "sandbox.tests.test_writer.BufferedWriteTests."
            "test_flush_returns_only_after_all_binary_chunks_are_durable"
        ),
    ),
)


def build_demo_specs(
    capture_id: str,
    max_turns: int,
    max_budget_usd: float,
    model: str,
) -> list[RunSpec]:
    """Build the immutable A1 → A2 → B1 → B2 → C1 → C2 Run plan."""
    return [
        RunSpec(
            run_id=f"{capture_id}-{bug.label}-{bug.bug_id}",
            bug_id=bug.bug_id,
            root_cause_class=bug.root_cause_class,
            tests_path=Path("sandbox/tests"),
            test_command=("python3", "-m", "unittest", bug.test_id, "-v"),
            max_turns=max_turns,
            max_budget_usd=max_budget_usd,
            model=model,
        )
        for bug in DEMO_BUGS
    ]


def validate_live_demo(
    events: Iterable[Mapping[str, Any]],
    capture_id: str,
) -> dict[str, Any]:
    """Validate all six factual histories and strict within-class improvements."""
    parsed = list(events)
    specs = build_demo_specs(
        capture_id=capture_id,
        max_turns=1,
        max_budget_usd=1.0,
        model="validation-only",
    )
    expected_run_ids = [spec.run_id for spec in specs]
    started_run_ids = [
        str(event.get("run_id"))
        for event in parsed
        if event.get("type") == "run_started"
    ]
    if started_run_ids != expected_run_ids:
        raise LiveDemoError(
            "run_started events must contain only the six Runs in the exact demo order"
        )

    pair_summaries: list[dict[str, Any]] = []
    for pair_index in range(0, len(specs), 2):
        research_id = specs[pair_index].run_id
        reuse_id = specs[pair_index + 1].run_id
        try:
            pair = validate_live_pair(parsed, research_id, reuse_id)
        except LivePairError as error:
            raise LiveDemoError(str(error)) from error

        research_finished = _finished(parsed, research_id)
        reuse_finished = _finished(parsed, reuse_id)
        research_tokens = _required_number(
            research_finished, "tokens", research_id
        )
        reuse_tokens = _required_number(reuse_finished, "tokens", reuse_id)
        if reuse_tokens >= research_tokens:
            raise LiveDemoError(
                f"Reuse Run '{reuse_id}' must use fewer tokens than '{research_id}'"
            )

        research_seconds = _required_number(
            research_finished, "seconds", research_id
        )
        reuse_seconds = _required_number(reuse_finished, "seconds", reuse_id)
        if reuse_seconds >= research_seconds:
            raise LiveDemoError(
                f"Reuse Run '{reuse_id}' must take less wall-clock time than "
                f"'{research_id}'"
            )

        if reuse_finished.get("sources_count") != 0:
            raise LiveDemoError(
                f"Reuse Run '{reuse_id}' must record sources_count=0"
            )

        pair_summaries.append(
            {
                "root_cause_class": specs[pair_index].root_cause_class,
                "run_ids": [research_id, reuse_id],
                "skill_id": pair["skill_id"],
                "research": {
                    "tokens": research_tokens,
                    "seconds": research_seconds,
                    "sources_count": research_finished.get("sources_count"),
                    "cost_usd": research_finished.get("cost_usd"),
                },
                "reuse": {
                    "tokens": reuse_tokens,
                    "seconds": reuse_seconds,
                    "sources_count": reuse_finished.get("sources_count"),
                    "cost_usd": reuse_finished.get("cost_usd"),
                },
            }
        )

    return {
        "capture_id": capture_id,
        "runs_completed": len(specs),
        "reuse_pairs": len(pair_summaries),
        "pairs": pair_summaries,
    }


def _finished(
    events: list[Mapping[str, Any]],
    run_id: str,
) -> Mapping[str, Any]:
    matching = [
        event
        for event in events
        if event.get("run_id") == run_id and event.get("type") == "run_finished"
    ]
    if len(matching) != 1:
        raise LiveDemoError(f"Run '{run_id}' must have exactly one run_finished event")
    return matching[0]


def _required_number(
    event: Mapping[str, Any],
    field: str,
    run_id: str,
) -> float | int:
    value = event.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise LiveDemoError(f"Run '{run_id}' must record numeric {field}")
    return value
