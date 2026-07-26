"""Generate a demo events.jsonl for the dashboard from the off_by_one problem.

Usage:
    agent/.venv/bin/python3 demo/codex-prototype/generate_demo_run.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent" / "src"))

from kintsugi_agent.events import EventLog  # noqa: E402
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEMO_DIR = Path(__file__).resolve().parent
RUN_ID = "codex-demo-off_by_one"


async def query_registry(hypothesis: str) -> dict:
    """Ask the Kintsugi Skill Registry over MCP whether a Skill exists."""
    skills_dir = DEMO_DIR / "skills"
    skills_dir.mkdir(exist_ok=True)
    params = StdioServerParameters(
        command=str(REPO / "registry" / ".venv" / "bin" / "kintsugi-registry"),
        args=[],
        env={
            **os.environ,
            "KINTSUGI_SKILLS_DIR": str(skills_dir),
            "KINTSUGI_SKILLS_REMOTE": "",
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_skills", {"hypothesis": hypothesis}
            )
            return result.structuredContent or {}


async def main() -> None:
    events_path = DEMO_DIR / "events.jsonl"
    events_path.unlink(missing_ok=True)
    events = EventLog(events_path, RUN_ID)

    hypothesis = (
        "An off-by-one slice boundary drops the newest item instead of keeping it."
    )

    await events.append(
        "run_started",
        bug_id="off_by_one",
        root_cause_class="Off-by-one slice boundary",
    )
    await events.append("hypothesis_formed", text=hypothesis)

    registry_response = await query_registry(hypothesis)
    decision = registry_response.get("decision", "research")
    matches = registry_response.get("matches") or []
    top_match = matches[0] if matches else {}
    await events.append(
        "registry_queried",
        decision=decision,
        top_score=top_match.get("score", 0.0),
        skill_id=top_match.get("id"),
    )

    source_url = "https://docs.python.org/3/reference/expressions.html#slicings"
    await events.append(
        "source_read",
        url=source_url,
        title="6.3.4. Slicings — Python Language Reference",
    )
    await events.append(
        "strategy_recorded",
        text="Use orders[-n:] rather than orders[-n - 1 : -1] so the slice keeps the most recent item.",
        sources=[source_url],
    )
    await events.append(
        "patch_applied",
        files_touched=["problems/off_by_one/inventory.py"],
    )
    await events.append(
        "tests_run",
        passed=1,
        failed=0,
        output_tail="Ran 1 test in 0.001s\n\nOK",
    )
    if decision == "research":
        await events.append(
            "skill_published",
            skill_id="off-by-one-slice-boundary",
            name="Off-by-one slice boundary",
        )
    else:
        await events.append(
            "skill_reused",
            skill_id=str(top_match.get("id", "")),
            name=str(top_match.get("name", "")),
        )
    await events.append(
        "run_finished",
        outcome="passed",
        tokens=41823,
        cost_usd=0.14,
        seconds=27.4,
        sources_count=1,
    )

    print(f"Wrote {events_path}")


if __name__ == "__main__":
    asyncio.run(main())
