"""Claude Agent SDK hooks that enforce and observe one Run."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from .events import EventLog


def _permission(decision: str, reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


class RunHooks:
    """Hook callbacks bound to one worktree and one event stream."""

    def __init__(self, worktree: Path, events: EventLog) -> None:
        self.worktree = Path(worktree).resolve()
        self.events = events

    async def pre_tool_use(
        self,
        input_data: dict[str, Any],
        _tool_use_id: str | None,
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        """Deny edits that violate worktree, test-integrity, or ordering rules."""
        tool_name = input_data.get("tool_name")
        if await self.events.verification_attempts() >= 2:
            latest_tests = await self.events.latest("tests_run")
            if latest_tests is not None and latest_tests["failed"] > 0:
                return {
                    "continue_": False,
                    "stopReason": "This Run exhausted its two verification attempts.",
                    **_permission(
                        "deny",
                        "This Run stops after two failed verification attempts.",
                    ),
                }

        if tool_name == "Bash":
            if await self.events.current_verification_passed():
                return _permission(
                    "deny",
                    "Bash is closed after passing verification so the verified source state cannot change.",
                )
            command = input_data.get("tool_input", {}).get("command", "")
            if isinstance(command, str) and _looks_like_verification(command):
                return _permission(
                    "deny",
                    "Use verify_fix for tests so committed tests are restored immediately before verification.",
                )
            return {}

        if isinstance(tool_name, str) and tool_name.endswith("__publish_skill"):
            registry_event = await self.events.latest("registry_queried")
            is_green_research = (
                registry_event is not None
                and registry_event["decision"] == "research"
                and await self.events.current_verification_passed()
            )
            if not is_green_research:
                return _permission(
                    "deny",
                    "A Skill may be published only after passing tests on the Research Path.",
                )
            raw_sources = input_data.get("tool_input", {}).get("sources")
            observed_sources = await self.events.source_urls()
            if (
                not isinstance(raw_sources, list)
                or not raw_sources
                or any(
                    not isinstance(source, str)
                    or not source
                    or source not in observed_sources
                    for source in raw_sources
                )
            ):
                return _permission(
                    "deny",
                    "Every published Skill citation must be a source read during this Research Run.",
                )
            return _permission(
                "allow",
                "The Research Path fix passed and its Skill citations were observed.",
            )

        if tool_name == "WebFetch":
            registry_event = await self.events.latest("registry_queried")
            if registry_event and registry_event["decision"] == "research":
                return {}
            return _permission(
                "deny",
                "WebFetch is available only after the Registry selects the Research Path.",
            )

        if tool_name not in {"Edit", "Write"}:
            return {}

        raw_path = input_data.get("tool_input", {}).get("file_path")
        if not isinstance(raw_path, str) or not raw_path:
            return _permission("deny", "Edit and Write require a target file path.")

        target = Path(raw_path)
        if not target.is_absolute():
            target = self.worktree / target
        target = target.resolve(strict=False)

        try:
            relative_target = target.relative_to(self.worktree)
        except ValueError:
            return _permission(
                "deny",
                "This Run may edit files only inside its isolated worktree.",
            )

        if "tests" in relative_target.parts:
            return _permission(
                "deny",
                "Tests are immutable during a Run; fix the source, not the test.",
            )

        hypothesis_recorded = await self.events.contains("hypothesis_formed")
        strategy_event = await self.events.latest("strategy_recorded")
        if (
            not hypothesis_recorded
            or strategy_event is None
            or not strategy_event["sources"]
        ):
            return _permission(
                "deny",
                "Record a Root Cause Hypothesis and a cited fix strategy before editing source.",
            )

        return _permission(
            "allow",
            "The Run has recorded its Root Cause Hypothesis and cited fix strategy.",
        )

    async def post_tool_use(
        self,
        input_data: dict[str, Any],
        _tool_use_id: str | None,
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        """Append the factual event corresponding to a completed tool call."""
        tool_name = str(input_data.get("tool_name", ""))
        tool_input = input_data.get("tool_input", {})
        if not isinstance(tool_input, dict):
            tool_input = {}
        response = _response_payload(input_data.get("tool_response"))

        if (
            tool_name.endswith("__record_hypothesis")
            and response.get("recorded") is True
        ):
            await self.events.append(
                "hypothesis_formed",
                text=str(tool_input.get("hypothesis", "")),
            )
        elif tool_name.endswith("__search_skills"):
            decision = response.get("decision")
            if decision not in {"research", "reuse"}:
                raw_response = input_data.get("tool_response")
                print(
                    "search_skills returned no usable decision; raw tool_response "
                    f"was: {raw_response!r}",
                    file=sys.stderr,
                )
                return {
                    "continue_": False,
                    "stopReason": (
                        "The Skill Registry returned an unrecognized response to "
                        "search_skills, so this Run cannot record a registry_queried "
                        "decision. Treating the Registry as unreachable and stopping "
                        "the Run rather than continuing without one."
                    ),
                }
            matches = response.get("matches", [])
            top_match = matches[0] if isinstance(matches, list) and matches else {}
            if not isinstance(top_match, dict):
                top_match = {}
            await self.events.append(
                "registry_queried",
                decision=decision,
                top_score=top_match.get("score", 0.0),
                skill_id=top_match.get("id"),
            )
        elif tool_name == "WebFetch":
            url = str(tool_input.get("url", ""))
            await self.events.append(
                "source_read",
                url=url,
                title=str(response.get("title") or url),
            )
        elif tool_name.endswith("__get_skill"):
            await self.events.remember_retrieved_skill(response)
        elif (
            tool_name.endswith("__record_strategy")
            and response.get("recorded") is True
        ):
            await self.events.append(
                "strategy_recorded",
                text=str(tool_input.get("strategy", "")),
                sources=list(tool_input.get("sources", [])),
            )
            reused_skill = response.get("reused_skill")
            if isinstance(reused_skill, dict):
                await self.events.append(
                    "skill_reused",
                    skill_id=str(reused_skill.get("id", "")),
                    name=str(reused_skill.get("name", "")),
                )
        elif tool_name in {"Edit", "Write"}:
            target = Path(str(tool_input.get("file_path", "")))
            if not target.is_absolute():
                target = self.worktree / target
            try:
                displayed_path = str(
                    target.resolve(strict=False).relative_to(self.worktree)
                )
            except ValueError:
                displayed_path = str(target)
            await self.events.append(
                "patch_applied",
                files_touched=[displayed_path],
            )
        elif tool_name.endswith("__verify_fix") and response.get("attempt"):
            await self.events.append(
                "tests_run",
                passed=int(response.get("passed_count", 0)),
                failed=int(response.get("failed_count", 0)),
                output_tail=str(response.get("output_tail", "")),
            )
            if (
                int(response.get("failed_count", 0)) > 0
                and await self.events.verification_attempts() >= 2
            ):
                return {
                    "continue_": False,
                    "stopReason": "This Run stopped after two failed verification attempts.",
                }
        elif tool_name.endswith("__publish_skill") and response.get("published") is True:
            await self.events.append(
                "skill_published",
                skill_id=str(response.get("skill_id", "")),
                name=str(tool_input.get("name", "")),
            )
        return {}


def _response_payload(response: object) -> dict[str, Any]:
    """Extract a JSON object from direct, string-encoded, or MCP-wrapped hook responses.

    An external stdio MCP tool's response arrives as a raw JSON-encoded string
    (confirmed against a real Run), not a dict; an in-process SDK tool's
    response arrives as a flat dict already.
    """
    if isinstance(response, str):
        try:
            parsed = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(response, dict):
        content = response.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if not isinstance(text, str):
                    continue
                try:
                    payload = json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(payload, dict):
                    return payload
        return response
    return {}


def _looks_like_verification(command: str) -> bool:
    patterns = (
        r"(^|[\s;&|])pytest(?:\s|$)",
        r"python(?:3(?:\.\d+)?)?\s+-m\s+unittest(?:\s|$)",
        r"(^|[\s;&|])(?:npm|pnpm|yarn)\s+(?:run\s+)?test(?:\s|$)",
        r"(^|[\s;&|])(?:cargo|go)\s+test(?:\s|$)",
        r"scripts/verify_[A-Za-z0-9_.-]*\.py",
    )
    return any(re.search(pattern, command) for pattern in patterns)
