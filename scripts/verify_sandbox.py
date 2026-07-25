#!/usr/bin/env python3
"""Verify every acceptance criterion for GitHub issue #3."""

from __future__ import annotations

import ast
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE = "baseline"


@dataclass(frozen=True)
class SeededBug:
    root_cause_class: str
    source_file: str
    function_name: str
    test_file: str
    test_name: str
    replacements: tuple[tuple[str, str], ...]

    @property
    def test_id(self) -> str:
        module = self.test_file.removesuffix(".py").replace("/", ".")
        return f"{module}.{self.test_name}"


BUGS = (
    SeededBug(
        root_cause_class="DST-boundary datetime arithmetic",
        source_file="sandbox/scheduling.py",
        function_name="next_run_at",
        test_file="sandbox/tests/test_scheduling.py",
        test_name=(
            "RecurringScheduleTests."
            "test_daily_run_keeps_its_local_appointment_after_spring_forward"
        ),
        replacements=(
            (
                "from datetime import datetime, timedelta, timezone",
                "from datetime import datetime, timedelta",
            ),
            (
                "    utc_candidate = previous_run.astimezone(timezone.utc) "
                "+ timedelta(hours=24)\n"
                "    return utc_candidate.astimezone(previous_run.tzinfo)",
                "    return previous_run + timedelta(days=1)",
            ),
        ),
    ),
    SeededBug(
        root_cause_class="DST-boundary datetime arithmetic",
        source_file="sandbox/reports.py",
        function_name="shift_duration",
        test_file="sandbox/tests/test_reports.py",
        test_name=(
            "WorkedTimeReportTests."
            "test_overnight_fallback_shift_counts_the_repeated_hour"
        ),
        replacements=(
            (
                "from datetime import datetime, timedelta",
                "from datetime import datetime, timedelta, timezone",
            ),
            (
                "    return window.ended_at - window.started_at",
                "    return window.ended_at.astimezone(timezone.utc) "
                "- window.started_at.astimezone(\n"
                "        timezone.utc\n"
                "    )",
            ),
        ),
    ),
    SeededBug(
        root_cause_class="money represented as float instead of Decimal",
        source_file="sandbox/checkout.py",
        function_name="total_with_tax",
        test_file="sandbox/tests/test_checkout.py",
        test_name=(
            "CheckoutTotalTests."
            "test_half_cent_tax_rounds_up_on_the_customer_charge"
        ),
        replacements=(
            (
                "from decimal import Decimal",
                "from decimal import Decimal, ROUND_HALF_UP",
            ),
            (
                "    subtotal = sum(float(item.unit_price) * item.quantity "
                "for item in items)\n"
                "    charged = round(subtotal * (1 + tax_percent / 100), 2)\n"
                "    return Decimal(str(charged))",
                "    subtotal = sum(\n"
                "        (Decimal(item.unit_price) * item.quantity "
                "for item in items), Decimal(\"0\")\n"
                "    )\n"
                "    multiplier = Decimal(\"1\") + Decimal(tax_percent) "
                "/ Decimal(\"100\")\n"
                "    return (subtotal * multiplier).quantize("
                "Decimal(\"0.01\"), rounding=ROUND_HALF_UP)",
            ),
        ),
    ),
    SeededBug(
        root_cause_class="money represented as float instead of Decimal",
        source_file="sandbox/payouts.py",
        function_name="split_evenly",
        test_file="sandbox/tests/test_payouts.py",
        test_name=(
            "PayoutAllocationTests."
            "test_three_recipient_distribution_preserves_the_entire_fund"
        ),
        replacements=(
            (
                "from decimal import Decimal",
                "from decimal import Decimal, ROUND_DOWN",
            ),
            (
                "    share = round(float(instruction.gross_amount) "
                "/ len(instruction.recipient_ids), 2)\n"
                "    return {\n"
                "        recipient_id: Decimal(str(share))\n"
                "        for recipient_id in instruction.recipient_ids\n"
                "    }",
                "    gross = Decimal(instruction.gross_amount)\n"
                "    recipient_count = len(instruction.recipient_ids)\n"
                "    share = (gross / recipient_count).quantize("
                "Decimal(\"0.01\"), rounding=ROUND_DOWN)\n"
                "    allocations = {recipient_id: share "
                "for recipient_id in instruction.recipient_ids}\n"
                "    allocations[instruction.recipient_ids[-1]] "
                "+= gross - share * recipient_count\n"
                "    return allocations",
            ),
        ),
    ),
    SeededBug(
        root_cause_class="asyncio exception semantics",
        source_file="sandbox/fetcher.py",
        function_name="fetch_all",
        test_file="sandbox/tests/test_fetcher.py",
        test_name=(
            "ConcurrentFetchTests.test_batch_request_surfaces_a_failed_dependency"
        ),
        replacements=(
            (
                "return_exceptions=True",
                "return_exceptions=False",
            ),
        ),
    ),
    SeededBug(
        root_cause_class="asyncio exception semantics",
        source_file="sandbox/writer.py",
        function_name="flush",
        test_file="sandbox/tests/test_writer.py",
        test_name=(
            "BufferedWriteTests."
            "test_flush_returns_only_after_all_binary_chunks_are_durable"
        ),
        replacements=(
            (
                "        sink.write(chunk)",
                "        await sink.write(chunk)",
            ),
        ),
    ),
)


def run(
    *command: str,
    cwd: Path = REPO_ROOT,
    expect_success: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise AssertionError(
            f"{' '.join(command)} failed with {result.returncode}:\n{result.stdout}"
        )
    return result


@contextmanager
def baseline_worktree() -> Iterator[Path]:
    temporary_root = Path(tempfile.mkdtemp(prefix="kintsugi-sandbox-"))
    worktree = temporary_root / "worktree"
    try:
        run(
            "git",
            "worktree",
            "add",
            "--quiet",
            "--detach",
            str(worktree),
            BASELINE,
        )
        yield worktree
    finally:
        if worktree.exists():
            run(
                "git",
                "worktree",
                "remove",
                "--force",
                str(worktree),
                expect_success=False,
            )
        shutil.rmtree(temporary_root, ignore_errors=True)


def function_signature(source: Path, function_name: str) -> str:
    tree = ast.parse(source.read_text())
    functions = (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )
    function = next(functions, None)
    if function is None:
        raise AssertionError(f"{function_name} is missing from {source}")

    annotations = [
        ast.dump(argument.annotation) if argument.annotation is not None else ""
        for argument in function.args.args
    ]
    return_annotation = (
        ast.dump(function.returns) if function.returns is not None else ""
    )
    return repr((annotations, return_annotation))


def test_assertion_shape(source: Path, test_name: str) -> tuple[str, ...]:
    method_name = test_name.split(".")[-1]
    tree = ast.parse(source.read_text())
    methods = (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == method_name
    )
    method = next(methods, None)
    if method is None:
        raise AssertionError(f"{test_name} is missing from {source}")

    assertions = sorted(
        {
            node.func.attr
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")
        }
    )
    if not assertions:
        raise AssertionError(f"{test_name} contains no unittest assertion")
    return tuple(assertions)


def verify_baseline_tag() -> None:
    baseline_commit = run("git", "rev-parse", f"{BASELINE}^{{commit}}").stdout.strip()
    tag_names = run("git", "tag", "--points-at", baseline_commit).stdout.splitlines()
    if BASELINE not in tag_names:
        raise AssertionError("baseline does not resolve to the seeded commit")

    expected_files = [bug.source_file for bug in BUGS] + [
        bug.test_file for bug in BUGS
    ]
    baseline_files = set(
        run("git", "ls-tree", "-r", "--name-only", BASELINE).stdout.splitlines()
    )
    missing = sorted(set(expected_files) - baseline_files)
    if missing:
        raise AssertionError(f"baseline is missing seeded files: {missing}")
    print(f"PASS tag: baseline -> {baseline_commit[:7]} with all 12 seeded files")


def verify_baseline_failures() -> None:
    with baseline_worktree() as worktree:
        result = run(
            "python3",
            "-m",
            "unittest",
            "discover",
            "-s",
            "sandbox/tests",
            "-v",
            cwd=worktree,
            expect_success=False,
        )
    summary = re.search(r"Ran (\d+) tests?", result.stdout)
    failures = re.search(r"FAILED \(failures=(\d+)\)", result.stdout)
    if result.returncode == 0 or summary is None or failures is None:
        raise AssertionError(f"baseline did not fail as expected:\n{result.stdout}")
    if (int(summary.group(1)), int(failures.group(1))) != (6, 6):
        raise AssertionError(f"expected 6/6 failures:\n{result.stdout}")
    for bug in BUGS:
        if bug.test_name.split(".")[-1] not in result.stdout:
            raise AssertionError(f"baseline output omitted {bug.test_name}")
    print("PASS baseline: 6 tests discovered; all 6 failed for their seeded reason")


def verify_pair_distinctness() -> None:
    grouped: dict[str, list[SeededBug]] = defaultdict(list)
    for bug in BUGS:
        grouped[bug.root_cause_class].append(bug)

    with baseline_worktree() as worktree:
        for root_cause_class, pair in grouped.items():
            if len(pair) != 2:
                raise AssertionError(f"{root_cause_class} does not have exactly 2 bugs")
            first, second = pair
            if first.source_file == second.source_file:
                raise AssertionError(f"{root_cause_class} reuses a source file")
            if first.function_name == second.function_name:
                raise AssertionError(f"{root_cause_class} reuses a function name")
            if first.test_name == second.test_name:
                raise AssertionError(f"{root_cause_class} reuses test wording")

            first_signature = function_signature(
                worktree / first.source_file, first.function_name
            )
            second_signature = function_signature(
                worktree / second.source_file, second.function_name
            )
            if first_signature == second_signature:
                raise AssertionError(f"{root_cause_class} reuses a function signature")

            first_test_shape = test_assertion_shape(
                worktree / first.test_file, first.test_name
            )
            second_test_shape = test_assertion_shape(
                worktree / second.test_file, second.test_name
            )
            if first_test_shape == second_test_shape:
                raise AssertionError(f"{root_cause_class} reuses a test shape")

            for bug in pair:
                test_source = (worktree / bug.test_file).read_text()
                if bug.test_name.split(".")[-1] not in test_source:
                    raise AssertionError(f"{bug.test_name} is missing from its test file")
            print(
                f"PASS distinctness: {root_cause_class} uses different files, "
                "functions, signatures, test wording, and assertion shapes"
            )


def apply_fix(worktree: Path, bug: SeededBug) -> None:
    source_path = worktree / bug.source_file
    source = source_path.read_text()
    for old, new in bug.replacements:
        if source.count(old) != 1:
            raise AssertionError(
                f"expected one fix target in {bug.source_file}: {old!r}"
            )
        source = source.replace(old, new)
    source_path.write_text(source)


def patch_size(worktree: Path, source_file: str) -> tuple[int, int]:
    output = run("git", "diff", "--numstat", "--", source_file, cwd=worktree).stdout
    match = re.fullmatch(r"(\d+)\t(\d+)\t.+\n?", output)
    if match is None:
        raise AssertionError(f"could not measure patch for {source_file}: {output!r}")
    return int(match.group(1)), int(match.group(2))


def verify_fixes_and_comparability() -> None:
    sizes: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for bug in BUGS:
        with baseline_worktree() as worktree:
            apply_fix(worktree, bug)
            test = run(
                "python3",
                "-m",
                "unittest",
                bug.test_id,
                "-v",
                cwd=worktree,
            )
            if "Ran 1 test" not in test.stdout or "\nOK\n" not in test.stdout:
                raise AssertionError(
                    f"fix did not produce one passing test:\n{test.stdout}"
                )
            added, deleted = patch_size(worktree, bug.source_file)
            changed = added + deleted
            sizes[bug.root_cause_class].append((bug.function_name, changed))
            print(
                f"PASS fix: {bug.function_name} -> 1/1 test passed; "
                f"patch +{added}/-{deleted} ({changed} changed lines)"
            )

    for root_cause_class, pair_sizes in sizes.items():
        changed_lines = [size for _, size in pair_sizes]
        size_ratio = max(changed_lines) / min(changed_lines)
        if size_ratio > 1.5:
            raise AssertionError(
                f"{root_cause_class} fixes are not comparable: {pair_sizes}"
            )
        print(
            f"PASS comparability: {root_cause_class} fixes differ by "
            f"{max(changed_lines) - min(changed_lines)} changed line(s) "
            f"({size_ratio:.2f}x)"
        )


def main() -> None:
    verify_baseline_tag()
    verify_baseline_failures()
    verify_pair_distinctness()
    verify_fixes_and_comparability()
    print(
        "VERIFICATION PASSED: 5/5 acceptance criteria; "
        "6/6 baseline failures; 6/6 intended fixes"
    )


if __name__ == "__main__":
    main()
