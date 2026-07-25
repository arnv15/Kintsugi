"""Pinned Claude Agent SDK loop for one Kintsugi Run."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookCallback,
    HookMatcher,
    ResultMessage,
)
from claude_agent_sdk.types import McpServerConfig

from .events import EventLog
from .hooks import RunHooks
from .runtime_tools import RuntimeTools, build_runtime_server

SDK_VERSION = "0.2.123"

BUILTIN_TOOLS = [
    "Read",
    "Edit",
    "Write",
    "Bash",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "Skill",
]

MCP_TOOLS = [
    "mcp__runtime__record_hypothesis",
    "mcp__runtime__record_strategy",
    "mcp__runtime__install_skill",
    "mcp__runtime__verify_fix",
    "mcp__skill-registry__search_skills",
    "mcp__skill-registry__get_skill",
    "mcp__skill-registry__publish_skill",
]

SYSTEM_PROMPT = """\
You execute one Kintsugi Run against one Seeded Bug. Follow this order exactly:

1. Inspect the configured failing test and relevant source without editing.
2. Form one Root Cause Hypothesis and call record_hypothesis.
3. Pass exactly that hypothesis to the Skill Registry's search_skills tool.
4. Obey the Registry's decision:
   - reuse: call get_skill, pass its selected id to install_skill, invoke the
     installed Skill, and do not call WebFetch.
   - research: use WebSearch to discover primary documentation and WebFetch to
     read it.
5. Call record_strategy with the fix strategy and its source URLs.
6. Edit source only. Never edit tests.
7. Call verify_fix; never run verification through Bash. If it fails, revise
   the source once and call verify_fix one final time.
8. After passing on the Research Path, publish one repo-agnostic Skill with the
   citations. After passing on the Reuse Path, do not publish another copy.
9. Stop after a pass or after the second failed verification.

The runtime hooks enforce ordering, test integrity, worktree isolation, path
choice, two attempts, and publish-only-on-green. Treat a hook denial as a
correction to follow, not as a reason to work around the runtime.
"""


def build_agent_options(
    worktree: Path,
    hooks: RunHooks,
    runtime_tools: RuntimeTools,
    registry_command: tuple[str, ...],
    registry_env: dict[str, str] | None = None,
    max_turns: int = 40,
    max_budget_usd: float | None = None,
    model: str | None = None,
) -> ClaudeAgentOptions:
    """Build the fully isolated, non-interactive SDK configuration."""
    if not registry_command:
        raise ValueError("registry_command must not be empty")

    registry: McpServerConfig = {
        "type": "stdio",
        "command": registry_command[0],
        "args": list(registry_command[1:]),
        "env": {
            **(registry_env or {}),
            "KINTSUGI_SANDBOX_REPO": str(worktree),
        },
    }
    runtime: McpServerConfig = {
        "type": "sdk",
        "name": "kintsugi-runtime",
        "instance": build_runtime_server(runtime_tools),
    }
    return ClaudeAgentOptions(
        cwd=worktree,
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": SYSTEM_PROMPT,
        },
        tools=BUILTIN_TOOLS,
        allowed_tools=[
            *(tool_name for tool_name in BUILTIN_TOOLS if tool_name != "Skill"),
            *MCP_TOOLS,
        ],
        mcp_servers={"skill-registry": registry, "runtime": runtime},
        strict_mcp_config=True,
        permission_mode="bypassPermissions",
        setting_sources=[],
        skills="all",
        hooks={
            "PreToolUse": [
                HookMatcher(
                    matcher=None,
                    hooks=[cast(HookCallback, hooks.pre_tool_use)],
                )
            ],
            "PostToolUse": [
                HookMatcher(
                    matcher=None,
                    hooks=[cast(HookCallback, hooks.post_tool_use)],
                )
            ],
        },
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        model=model,
        sandbox={
            "enabled": True,
            "autoAllowBashIfSandboxed": True,
            "allowUnsandboxedCommands": False,
        },
        env={"CLAUDE_AGENT_SDK_CLIENT_APP": f"kintsugi-agent/{SDK_VERSION}"},
    )


async def run_sdk_loop(
    options: object,
    prompt: str,
    client_factory: Callable[..., Any] = ClaudeSDKClient,
) -> ResultMessage:
    """Run one SDK conversation and return its final metrics message."""
    final_result: ResultMessage | None = None
    async with client_factory(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                final_result = message

    if final_result is None:
        raise RuntimeError("Claude Agent SDK ended without a ResultMessage")
    return final_result


async def finish_run(
    events: EventLog,
    result: ResultMessage,
    seconds: float,
) -> dict[str, Any]:
    """Append the factual Run outcome and SDK metrics."""
    passed = await events.current_verification_passed()
    return await events.append(
        "run_finished",
        outcome="passed" if passed else "failed",
        tokens=_total_tokens(result.usage),
        cost_usd=result.total_cost_usd,
        seconds=seconds,
        sources_count=await events.source_count(),
    )


def _total_tokens(usage: dict[str, Any] | None) -> int | None:
    if not usage:
        return None
    token_fields = (
        "input_tokens",
        "output_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
    )
    values = [
        value
        for field in token_fields
        if isinstance((value := usage.get(field)), int)
    ]
    return sum(values) if values else None
