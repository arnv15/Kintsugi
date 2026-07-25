"""`search_skills` accepts a Root Cause Hypothesis and nothing else.

ADR-0003 makes "diagnose before you look up" a mechanism rather than an
instruction: a query carrying a traceback, a file path or a line number is
refused outright, so an agent cannot skip diagnosis and search on error text.
"""

import pytest

from kintsugi_registry import registry as registry_module
from kintsugi_registry.errors import HypothesisRejected
from kintsugi_registry.registry import SkillRegistry

# Embeds one of the stored Skill's aliases verbatim, so matching this text would
# score near 100. It must still be refused, rather than coming back as a `reuse`
# the agent never diagnosed its way to.
TRACEBACK_QUOTING_A_STORED_ALIAS = (
    "Traceback (most recent call last):\n"
    '  File "app/checkout.py", line 42, in add_item\n'
    "    basket.append(sku)\n"
    "ValueError: default argument keeps values from a previous call"
)


def test_a_traceback_is_refused_even_when_its_text_would_match_a_stored_skill(
    populated_registry: SkillRegistry,
) -> None:
    assert (
        populated_registry.search_skills(
            "default argument keeps values from a previous call"
        )["decision"]
        == "reuse"
    ), "precondition: this wording matches a stored Skill when it arrives as prose"

    with pytest.raises(HypothesisRejected):
        populated_registry.search_skills(TRACEBACK_QUOTING_A_STORED_ALIAS)


def test_the_refusal_happens_before_any_matching_runs(
    populated_registry: SkillRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acceptance criterion is a claim about order, not just about outcome.

    Refusing a traceback proves nothing about ordering on its own — a matcher
    running first would score it and the guard would still refuse afterwards.
    So this reaches one level past the tool boundary and makes the matcher fail
    if it is ever reached, which is the only way the ordering can be observed.
    """

    def matcher_that_must_not_run(*_args: object, **_kwargs: object) -> list[object]:
        raise AssertionError("the matcher ran before the query shape was checked")

    monkeypatch.setattr(registry_module, "rank_skills", matcher_that_must_not_run)

    with pytest.raises(HypothesisRejected):
        populated_registry.search_skills(TRACEBACK_QUOTING_A_STORED_ALIAS)


@pytest.mark.parametrize(
    "query",
    [
        pytest.param(
            "Traceback (most recent call last): ZeroDivisionError: division by zero",
            id="traceback",
        ),
        pytest.param(
            "the totals are wrong in src/billing/invoice.py when a discount applies",
            id="relative-file-path",
        ),
        pytest.param(
            "something in /usr/local/lib/python3.11/dataclasses is mutating the default",
            id="absolute-path",
        ),
        pytest.param(
            "the accumulation happens at line 42 of the helper",
            id="line-number",
        ),
        pytest.param(
            "the failure comes from checkout:88:12 in the second call",
            id="line-and-column",
        ),
        pytest.param("   ", id="blank"),
    ],
)
def test_queries_that_are_not_a_root_cause_hypothesis_are_refused(
    populated_registry: SkillRegistry, query: str
) -> None:
    with pytest.raises(HypothesisRejected):
        populated_registry.search_skills(query)


def test_the_refusal_says_what_to_send_instead(populated_registry: SkillRegistry) -> None:
    with pytest.raises(HypothesisRejected) as refusal:
        populated_registry.search_skills(TRACEBACK_QUOTING_A_STORED_ALIAS)

    message = str(refusal.value)
    assert "traceback" in message.lower()
    assert "hypothesis" in message.lower()


@pytest.mark.parametrize(
    "hypothesis",
    [
        pytest.param(
            "a mutable list is used as a default parameter value, so it persists across calls",
            id="plain-prose",
        ),
        pytest.param(
            "the values accumulate between calls, e.g. the second call already sees the "
            "first call's entries",
            id="prose-containing-e.g.",
        ),
        pytest.param(
            "the computation returns 3.14 where the caller expected a whole number, "
            "because of read/write rounding in the accumulator",
            id="prose-containing-decimals-and-a-slash",
        ),
        pytest.param(
            "every line of the report shares one accumulator object",
            id="prose-containing-the-word-line",
        ),
    ],
)
def test_ordinary_prose_diagnoses_are_not_refused(
    populated_registry: SkillRegistry, hypothesis: str
) -> None:
    result = populated_registry.search_skills(hypothesis)

    assert result["decision"] in {"reuse", "research"}
