"""In-process MCP tools that expose Run state transitions to the agent."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .events import EventLog
from .verification import VerificationRunner


class RuntimeTools:
    """Operations owned by the runtime rather than the model or Registry."""

    def __init__(
        self,
        worktree: Path,
        events: EventLog,
        verifier: VerificationRunner,
    ) -> None:
        self.worktree = Path(worktree)
        self.events = events
        self.verifier = verifier
        self._installed_skill: tuple[str, str, set[str]] | None = None

    async def record_hypothesis(self, hypothesis: str) -> dict[str, Any]:
        if not hypothesis.strip():
            return {
                "recorded": False,
                "feedback": "State one Root Cause Hypothesis in prose.",
            }
        return {"recorded": True, "hypothesis": hypothesis.strip()}

    async def record_strategy(
        self, strategy: str, sources: list[str]
    ) -> dict[str, Any]:
        if not await self.events.contains("hypothesis_formed"):
            return {
                "recorded": False,
                "feedback": "Record a Root Cause Hypothesis before the fix strategy.",
            }
        usable_sources = [source.strip() for source in sources if source.strip()]
        if not strategy.strip() or not usable_sources:
            return {
                "recorded": False,
                "feedback": "A fix strategy needs prose and at least one primary-source URL.",
            }
        registry_event = await self.events.latest("registry_queried")
        if registry_event is None:
            return {
                "recorded": False,
                "feedback": "Query the Skill Registry before recording a fix strategy.",
            }
        if registry_event["decision"] == "research":
            allowed_sources = await self.events.source_urls()
            provenance = "WebFetch calls from this Research Path"
        elif self._installed_skill is not None:
            _, _, allowed_sources = self._installed_skill
            provenance = "the Skill installed for this Reuse Path"
        else:
            return {
                "recorded": False,
                "feedback": "Install the Registry-selected Skill before recording its strategy.",
            }
        unobserved = sorted(set(usable_sources) - allowed_sources)
        if unobserved:
            return {
                "recorded": False,
                "feedback": (
                    "Every strategy source must come from "
                    f"{provenance}; these were not observed: {', '.join(unobserved)}"
                ),
            }
        result: dict[str, Any] = {
            "recorded": True,
            "strategy": strategy.strip(),
            "sources": usable_sources,
        }
        if self._installed_skill is not None:
            skill_id, name, _ = self._installed_skill
            result["reused_skill"] = {"id": skill_id, "name": name}
        return result

    async def install_skill(
        self,
        skill_id: str,
    ) -> dict[str, Any]:
        decision = await self.events.latest("registry_queried")
        if (
            decision is None
            or decision["decision"] != "reuse"
            or decision["skill_id"] != skill_id
        ):
            return {
                "installed": False,
                "feedback": "Install only the Skill selected by the Registry's Reuse decision.",
            }
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", skill_id):
            return {
                "installed": False,
                "feedback": "The Skill id must be a safe single directory name.",
            }
        retrieved = await self.events.retrieved_skill(skill_id)
        if retrieved is None:
            return {
                "installed": False,
                "feedback": "Call get_skill for the Registry-selected id before installing it.",
            }
        name = str(retrieved["name"])
        document = str(retrieved["document"])
        usable_sources = {str(source) for source in retrieved["sources"]}

        destination = self.worktree / ".claude" / "skills" / skill_id / "SKILL.md"
        destination.parent.mkdir(parents=True, exist_ok=False)
        destination.write_text(document, encoding="utf-8")
        self._installed_skill = (skill_id, name, usable_sources)
        return {
            "installed": True,
            "skill_id": skill_id,
            "name": name,
            "path": str(destination),
        }

    async def verify_fix(self) -> dict[str, Any]:
        return await self.verifier.verify()


def build_runtime_server(runtime: RuntimeTools) -> Any:
    """Build the in-process SDK MCP server used by the live agent loop."""
    from claude_agent_sdk import create_sdk_mcp_server, tool

    @tool(
        "record_hypothesis",
        "Record one Root Cause Hypothesis before querying the Skill Registry.",
        {"hypothesis": str},
    )
    async def record_hypothesis(args: dict[str, Any]) -> dict[str, Any]:
        return _tool_result(
            await runtime.record_hypothesis(hypothesis=str(args["hypothesis"]))
        )

    @tool(
        "record_strategy",
        "Record a cited fix strategy before editing source.",
        {
            "type": "object",
            "properties": {
                "strategy": {"type": "string"},
                "sources": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["strategy", "sources"],
            "additionalProperties": False,
        },
    )
    async def record_strategy(args: dict[str, Any]) -> dict[str, Any]:
        return _tool_result(
            await runtime.record_strategy(
                strategy=str(args["strategy"]),
                sources=[str(source) for source in args["sources"]],
            )
        )

    @tool(
        "install_skill",
        "Install the authoritative get_skill response selected by the Registry into this Run.",
        {"skill_id": str},
    )
    async def install_skill(args: dict[str, Any]) -> dict[str, Any]:
        return _tool_result(
            await runtime.install_skill(
                skill_id=str(args["skill_id"]),
            )
        )

    @tool(
        "verify_fix",
        "Restore committed tests and run the configured verification command. At most two calls execute.",
        {},
    )
    async def verify_fix(_args: dict[str, Any]) -> dict[str, Any]:
        return _tool_result(await runtime.verify_fix())

    return create_sdk_mcp_server(
        name="kintsugi-runtime",
        version="0.1.0",
        tools=[record_hypothesis, record_strategy, install_skill, verify_fix],
    )


def _tool_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, separators=(",", ":")),
            }
        ]
    }
