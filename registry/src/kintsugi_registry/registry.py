"""The Skill Registry's four operations, as the MCP tool boundary sees them.

Every method here returns exactly the payload the matching MCP tool returns, so
tests exercise the same surface an agent does. `server.py` is a thin adapter
over this class and holds no logic of its own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import SANDBOX_REPO_ENV_VAR, resolve_sandbox_repo
from .errors import RegistryError, SkillNotFound
from .hypothesis import require_root_cause_hypothesis
from .leakcheck import Leak, find_leaks
from .matching import DEFAULT_THRESHOLD, rank_skills
from .skill import Skill, slugify
from .store import SkillStore
from .sync import build_sync

UNKNOWN_PUBLISHER = "unknown"

RECOMMENDED_ALIASES = 3
"""Below this, a Skill is published with a warning rather than refused.

ADR-0003 leans on aliases heavily — vocabulary is what `token_set_ratio` is
unforgiving about — but the spec names exactly one mechanical publish-time
rejection, the repo-leak guard. Inventing a second one risks refusing a sound
Skill mid-Run, so a thin Skill publishes and says so.
"""


class SkillRegistry:
    """The shared store of Skills, reachable by any agent over MCP."""

    def __init__(self, skills_dir: Path, threshold: float = DEFAULT_THRESHOLD) -> None:
        self.store = SkillStore(Path(skills_dir))
        self.threshold = threshold
        self.sync = build_sync(self.store.root)

    def refresh(self) -> dict[str, Any]:
        """Bring the Skill directory up to date with the shared repo.

        Called when the server starts rather than on every search: ADR-0006
        reports wall-clock per Run, and a network round trip inside
        `search_skills` would land inside the number being measured.
        """
        outcome = self.sync.refresh()
        return {"detail": outcome.detail}

    def clear(self) -> list[str]:
        """Remove every Skill, returning the ids removed.

        Not exposed as an MCP tool: an agent has no reason to empty the shared
        Registry, and issue #8 needs this from a rehearsal script, not from a Run.
        """
        return self.store.clear()

    def search_skills(self, hypothesis: str) -> dict[str, Any]:
        """Decide, for one Root Cause Hypothesis, whether to reuse or research.

        The `decision` is the Registry's and never the caller's to compute
        (ADR-0003) — which is also why a caller that receives `research` gets
        nothing below the threshold to reconsider.
        """
        hypothesis = require_root_cause_hypothesis(hypothesis)
        matches = rank_skills(hypothesis, self.store.load_all().skills, self.threshold)
        return {
            "decision": "reuse" if matches else "research",
            "threshold": self.threshold,
            "matches": [
                {
                    "id": match.skill.id,
                    "name": match.skill.name,
                    "description": match.skill.description,
                    "score": match.score,
                    "matched_on": match.matched_on,
                }
                for match in matches
            ],
        }

    def list_skills(self) -> dict[str, Any]:
        """Every Skill in the Registry, without bodies.

        `unreadable` names any Skill directory whose document could not be
        parsed. Those are skipped everywhere else, so this is where an operator
        finds out a Skill is silently missing from search.
        """
        contents = self.store.load_all()
        return {
            "count": len(contents.skills),
            "skills": [
                {
                    "id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "aliases": skill.aliases,
                }
                for skill in contents.skills
            ],
            "unreadable": contents.unreadable,
        }

    def get_skill(self, skill_id: str) -> dict[str, Any]:
        """One Skill in full, including the installable document text."""
        skill = self.store.load(skill_id)
        if skill is None:
            raise SkillNotFound(
                f"No Skill with id '{skill_id}'. Call list_skills to see the available ids."
            )
        return _skill_payload(skill)

    def publish_skill(
        self,
        name: str,
        description: str,
        aliases: list[str],
        body: str,
        sources: list[str] | None = None,
        published_by: str = UNKNOWN_PUBLISHER,
        repo_path: str | None = None,
    ) -> dict[str, Any]:
        """Add a Skill to the Registry, or refuse it with feedback to act on.

        A refusal is a step in a retry loop, not a failure: it names every
        problem at once so one rewrite can clear them all.
        """
        problems = _validate(name, description, body)
        if problems:
            return _rejection(problems)

        repo = resolve_sandbox_repo(repo_path)
        leaks = self._find_leaks(body, repo)
        if leaks:
            return _leak_rejection(leaks)

        skill = Skill(
            id=slugify(name),
            name=name.strip(),
            description=description.strip(),
            aliases=list(aliases),
            sources=list(sources or []),
            published_by=published_by,
            body=body,
        )

        replaced = self.store.exists(skill.id)
        self.store.save(skill)
        # Sync only after the Skill is safely on disk, so a failure to reach the
        # shared repo costs the push and never the Skill itself.
        pushed = self.sync.record(skill.id, skill.published_by)
        return {
            "published": True,
            "skill_id": skill.id,
            "replaced": replaced,
            "leak_check": "passed" if repo else "skipped",
            "warnings": _warnings(skill.aliases, skill.sources, skill.published_by),
            "sync": {"pushed": pushed.pushed, "detail": pushed.detail},
        }

    def _find_leaks(self, body: str, repo: Path | None) -> list[Leak]:
        """Run the repo-leak guard, or record that there was nothing to run it against.

        No repo at all is reported as `leak_check: skipped` rather than quietly
        passing, so the audit trail never shows a guard that did not run as a
        guard that was satisfied. A repo that was named but cannot be read
        raises instead: a wrong path must not become a quiet way to publish
        unchecked.
        """
        if repo is None:
            return []

        if not repo.is_dir():
            raise RegistryError(
                f"repo_path '{repo}' is not a directory, so the Skill could not be checked "
                "for code carried out of the repo it was learned in. Pass the path of the "
                f"repo the bug was fixed in, or unset ${SANDBOX_REPO_ENV_VAR}."
            )
        return find_leaks(body, repo)


def _skill_payload(skill: Skill) -> dict[str, Any]:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "aliases": skill.aliases,
        "sources": skill.sources,
        "published_by": skill.published_by,
        "body": skill.body,
        "document": skill.render_document(),
    }


def _validate(name: str, description: str, body: str) -> list[str]:
    """Collect every problem at once, so a retry can fix them in one pass."""
    problems = []
    if not name.strip():
        problems.append("The Skill needs a 'name' naming its Root Cause Class.")
    elif not slugify(name):
        problems.append(
            f"The name '{name}' has no letters or digits, so no Skill id can be derived from it."
        )
    if not description.strip():
        problems.append(
            "The Skill needs a 'description' stating the Root Cause Class in prose — it is "
            "what search_skills matches a Root Cause Hypothesis against."
        )
    if not body.strip():
        problems.append(
            "The Skill needs a prose 'body' describing how bugs of this class are fixed."
        )
    return problems


def _warnings(aliases: list[str], sources: list[str], published_by: str) -> list[str]:
    """Things that weaken a published Skill without making it unusable."""
    warnings = []
    usable_aliases = [alias for alias in aliases if alias.strip()]
    if len(usable_aliases) < RECOMMENDED_ALIASES:
        warnings.append(
            f"This Skill has {len(usable_aliases)} alias(es); {RECOMMENDED_ALIASES} or more is "
            "much safer. Each alias is another phrasing a future Root Cause Hypothesis can "
            "reach this Skill by, and matching is unforgiving about vocabulary."
        )
    if not sources:
        warnings.append(
            "This Skill carries no 'sources'. An agent that reuses it inherits them as the "
            "citation for its own fix, so a Skill without any leaves that agent with none."
        )
    if published_by == UNKNOWN_PUBLISHER:
        warnings.append(
            "This Skill has no 'published_by'. Provenance is what makes 'who learned this' "
            "answerable once more than one agent publishes."
        )
    return warnings


def _rejection(problems: list[str], leaks: list[Leak] | None = None) -> dict[str, Any]:
    """Shape a refusal so publishing stays a retry loop, never a hard failure."""
    return {
        "published": False,
        "skill_id": None,
        "feedback": " ".join(problems),
        "problems": problems,
        "leaked_snippets": [
            {"snippet": leak.snippet, "found_in": leak.found_in} for leak in (leaks or [])
        ],
    }


def _leak_rejection(leaks: list[Leak]) -> dict[str, Any]:
    """Refuse a Skill carrying repo code, and say precisely what to rewrite."""
    collisions = ", ".join(f"'{leak.found_in}'" for leak in leaks)
    problems = [
        f"{len(leaks)} code block(s) in the body appear verbatim in the repo this Skill was "
        f"learned in ({collisions}), so the Skill would carry that repo's code with it.",
        "Rewrite each illustration synthetically: invent names, types and a domain the bug "
        "never touched, keeping only the shape of the mistake and the shape of the fix. The "
        "Skill has to teach the Root Cause Class to an agent working on a repo it has never "
        "seen, so nothing specific to this one belongs in it.",
    ]
    return _rejection(problems, leaks)
