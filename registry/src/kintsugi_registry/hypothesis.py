"""The guard that keeps `search_skills` a hypothesis-only interface.

ADR-0003: the Registry accepts one sentence of the agent's own diagnosis, never
the error text. This runs before any matching, so a query carrying a traceback
cannot match a Skill even when the traceback happens to quote one.

The rules are deliberately the three named in the ADR — traceback, file path,
line number — and each is written to fire on the shape of machine output rather
than on words that also occur in ordinary prose ("every line of the report",
"3.14", "read/write" and "e.g." all pass).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import HypothesisRejected

_SOURCE_EXTENSIONS = (
    "py|pyi|js|jsx|ts|tsx|java|kt|go|rb|rs|c|cc|cpp|cxx|h|hpp|cs|php|swift|scala|m|mm|"
    "sh|bash|zsh|sql|json|ya?ml|toml|ini|cfg|xml|html|css|scss|md|txt|log|lock"
)

EXAMPLE_HYPOTHESIS = (
    "a mutable object is used as a default parameter value, so it is shared across calls"
)


@dataclass(frozen=True)
class ForbiddenShape:
    name: str
    pattern: re.Pattern[str]
    complaint: str


FORBIDDEN_SHAPES: tuple[ForbiddenShape, ...] = (
    ForbiddenShape(
        name="traceback",
        pattern=re.compile(r"\btraceback\b", re.IGNORECASE),
        complaint="it contains a traceback",
    ),
    ForbiddenShape(
        name="file-path",
        pattern=re.compile(
            # A filename with a source extension, optionally with directories:
            # "invoice.py", "src/billing/invoice.py", "app\\models.rb".
            rf"(?<![\w.])[\w.\-/\\]*\w\.(?:{_SOURCE_EXTENSIONS})\b"
            # A rooted or relative path: "/usr/local/lib/x", "./src/x", "~/x".
            r"|(?<![\w~./\\])(?:~|\.{1,2})?/[\w.\-]+(?:/[\w.\-]+)+"
            # A Windows path: "C:\\Users\\x".
            r"|(?<![\w])[A-Za-z]:\\[\w.\-\\]+",
            re.IGNORECASE,
        ),
        complaint="it contains a file path",
    ),
    ForbiddenShape(
        name="line-number",
        pattern=re.compile(
            # "line 42", "line #42", "lines 8-12".
            r"\blines?\s*#?\s*\d+"
            # "checkout:88:12" — a line:column pair.
            r"|:\d+:\d+"
            # "#L42" — a source-host line anchor.
            r"|#L\d+\b",
            re.IGNORECASE,
        ),
        complaint="it contains a line number",
    ),
)


def require_root_cause_hypothesis(query: str) -> str:
    """Return the query if it is a hypothesis, otherwise refuse it.

    Refuses by raising rather than by returning a `research` decision: a caller
    told to research would simply research, and the guard would have enforced
    nothing.
    """
    hypothesis = query.strip()
    if not hypothesis:
        raise HypothesisRejected(
            "An empty query is not a Root Cause Hypothesis. Send one sentence of your own "
            f"diagnosis naming the kind of mistake — for example: {EXAMPLE_HYPOTHESIS!r}."
        )

    complaints = [shape.complaint for shape in FORBIDDEN_SHAPES if shape.pattern.search(hypothesis)]
    if complaints:
        raise HypothesisRejected(
            f"That query is not a Root Cause Hypothesis: {_join(complaints)}. "
            "Diagnose first, then send one sentence of your own diagnosis naming the kind of "
            f"mistake, with no error text, paths or line numbers — for example: "
            f"{EXAMPLE_HYPOTHESIS!r}."
        )

    return hypothesis


def _join(complaints: list[str]) -> str:
    if len(complaints) == 1:
        return complaints[0]
    return f"{', '.join(complaints[:-1])} and {complaints[-1]}"
