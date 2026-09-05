"""The Skill Registry as an MCP server.

A thin adapter: every tool below forwards to one `SkillRegistry` method and adds
nothing. The docstrings are not internal notes — they are the tool descriptions
the calling agent reads, so they state the contract the agent has to work
within (a hypothesis and nothing else; the decision is the Registry's).
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from .config import resolve_skills_dir, resolve_skills_remote
from .events import build_event_log, resolve_events_path
from .hypothesis import EXAMPLE_HYPOTHESIS
from .registry import SkillRegistry
from .sync import ensure_clone

# Carried as data rather than as a docstring so the worked example stays the one
# the refusal message hands back — a caller shown one sentence and corrected
# with a different one has to guess which is authoritative.
SEARCH_SKILLS_DESCRIPTION = f"""\
Decide whether a Skill already exists for a Root Cause Hypothesis.

Pass one sentence of your own diagnosis, naming in prose the kind of mistake you
believe you are looking at — for example: "{EXAMPLE_HYPOTHESIS}".

Do not pass a traceback, an exception message, a file path or a line number:
such a query is refused, because matching on surface text finds surface
resemblance and two bugs of the same Root Cause Class are deliberately unalike
on the surface.

Returns `decision: "reuse"` with the matching Skills, best first, or
`decision: "research"` with no matches. The decision is the Registry's; it is
not yours to recompute from the scores.
"""

INSTRUCTIONS = """\
The Kintsugi Skill Registry: a shared store of Skills, each describing one Root
Cause Class — a kind of programming mistake, independent of where it appears or
how it surfaces — and how bugs of that class are fixed.

Before fixing a bug, diagnose it: write one sentence naming the kind of mistake
you believe you are looking at, and pass that sentence to `search_skills`. The
Registry answers `reuse` (a Skill exists — adopt its fix strategy) or `research`
(none exists — research the class from primary sources, and publish what you
learn once your fix passes its tests).
"""


def build_server(registry: SkillRegistry) -> FastMCP:
    """Wrap a Registry in its MCP tool surface."""
    mcp = FastMCP("kintsugi-skill-registry", instructions=INSTRUCTIONS)

    @mcp.tool(description=SEARCH_SKILLS_DESCRIPTION)
    def search_skills(hypothesis: str) -> dict[str, Any]:
        return registry.search_skills(hypothesis)

    @mcp.tool()
    def get_skill(skill_id: str) -> dict[str, Any]:
        """Fetch one Skill in full, by the id `search_skills` returned.

        The `document` field is a complete, installable `SKILL.md`: write it to
        `.claude/skills/<id>/SKILL.md` to load the Skill natively. The `sources`
        field carries the citations the Skill was researched from — on the Reuse
        Path those are the citations for your fix.
        """
        return registry.get_skill(skill_id)

    @mcp.tool()
    def list_skills() -> dict[str, Any]:
        """List every Skill in the Registry, without bodies.

        For browsing and for operators. Do not use it to decide whether to reuse
        a Skill — that decision belongs to `search_skills`.
        """
        return registry.list_skills()

    @mcp.tool()
    def publish_skill(
        name: str,
        description: str,
        aliases: list[str],
        body: str,
        sources: list[str] | None = None,
        published_by: str = "unknown",
        repo_path: str | None = None,
    ) -> dict[str, Any]:
        """Publish a Skill for one Root Cause Class. Only ever after tests pass.

        - `name`: the Root Cause Class, named as a short noun phrase.
        - `description`: the class stated in prose, in the vocabulary a future
          agent would use to describe its own diagnosis. This is what a Root
          Cause Hypothesis is matched against.
        - `aliases`: at least three other phrasings of the same class. Vocabulary
          matters more than you expect — each alias is another way a differently
          worded hypothesis can reach this Skill.
        - `body`: prose describing how bugs of this class are fixed. It may
          include a short illustrative before/after snippet.
        - `sources`: the primary sources you read. A later agent inherits them as
          the citation for its own fix.
        - `repo_path`: the repo this Skill was learned in. Any code block over
          two lines that appears verbatim in it is refused — a Skill must teach
          the class to an agent working on a repo it has never seen, so write
          illustrations synthetically rather than pasting the diff you just made.

        A refusal returns `published: false` with `feedback` to act on. Rewrite
        and call again; it is a retry loop, not a failure.
        """
        return registry.publish_skill(
            name=name,
            description=description,
            aliases=aliases,
            body=body,
            sources=sources,
            published_by=published_by,
            repo_path=repo_path,
        )

    return mcp


def main() -> None:
    """Run the Registry over stdio, the transport an agent's MCP client speaks.

    Progress goes to stderr, never stdout: on stdio transport, stdout carries
    the MCP frames and a stray `print` would corrupt the protocol.
    """
    skills_dir = resolve_skills_dir()
    print(ensure_clone(skills_dir, resolve_skills_remote()), file=sys.stderr)

    events_path = resolve_events_path()
    session_id = new_session_id()
    registry = SkillRegistry(
        skills_dir=skills_dir,
        events=build_event_log(events_path, session_id),
    )
    print(registry.refresh()["detail"], file=sys.stderr)
    print(
        f"Recording events as session '{session_id}' in {events_path}."
        if events_path is not None
        else "No event log configured; set $KINTSUGI_EVENTS_PATH to record one.",
        file=sys.stderr,
    )

    build_server(registry).run()


def new_session_id() -> str:
    """Name one agent's connection to the Registry.

    One server process is one client's stdio connection, so the process lifetime
    is the closest thing to a session the Registry can observe. The timestamp
    makes a log readable in order; the suffix keeps two agents that connect in
    the same second apart.
    """
    return f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"


if __name__ == "__main__":  # pragma: no cover
    main()
