"""Fuzzy matching of a Root Cause Hypothesis against stored Skills.

Both sides of the comparison are prose about a root cause, which is what makes
plain token-set matching work here where matching on error text would not
(ADR-0003). A Skill is scored on its `description` and on each of its `aliases`,
and keeps its best score — each alias is another shot on goal for a hypothesis
phrased in different vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz, utils

from .skill import Skill

DEFAULT_THRESHOLD = 70.0
"""Score at or above which the Registry returns `reuse`. See ADR-0003."""

DESCRIPTION_FIELD = "description"


@dataclass(frozen=True)
class Match:
    skill: Skill
    score: float
    matched_on: str
    """The `description` marker, or the alias text that scored best."""


def score_skill(hypothesis: str, skill: Skill) -> Match:
    """Score one Skill, keeping whichever of its phrasings matched best."""
    candidates = [(DESCRIPTION_FIELD, skill.description)]
    candidates += [(alias, alias) for alias in skill.aliases if alias.strip()]

    best_label, best_score = DESCRIPTION_FIELD, 0.0
    for label, text in candidates:
        score = fuzz.token_set_ratio(hypothesis, text, processor=utils.default_process)
        if score > best_score:
            best_label, best_score = label, score

    return Match(skill=skill, score=round(best_score, 1), matched_on=best_label)


def rank_skills(
    hypothesis: str, skills: list[Skill], threshold: float = DEFAULT_THRESHOLD
) -> list[Match]:
    """Skills scoring at or above the threshold, best first.

    Below-threshold Skills are dropped rather than returned: the decision is the
    Registry's, and handing the caller material it could argue with would give
    that decision back.
    """
    matches = [score_skill(hypothesis, skill) for skill in skills]
    above = [match for match in matches if match.score >= threshold]
    return sorted(above, key=lambda match: (-match.score, match.skill.id))
