"""Top-level orchestration for one isolated Kintsugi Run."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from claude_agent_sdk import ResultMessage

from .events import EventLog
from .hooks import RunHooks
from .runner import build_agent_options, finish_run, run_sdk_loop
from .runtime_tools import RuntimeTools
from .verification import VerificationRunner
from .worktrees import WorktreeManager


class CreatesWorktrees(Protocol):
    async def create(self, run_id: str) -> Path: ...


OptionsBuilder = Callable[..., object]
SDKLoop = Callable[..., Awaitable[ResultMessage]]


@dataclass(frozen=True)
class RunSpec:
    """Operator-supplied facts needed to attempt one Seeded Bug."""

    run_id: str
    bug_id: str
    root_cause_class: str
    tests_path: Path
    test_command: tuple[str, ...]
    max_turns: int = 40
    max_budget_usd: float | None = None
    model: str | None = None


@dataclass(frozen=True)
class RunOutcome:
    """Inspectable locations and outcome returned to the operator."""

    run_id: str
    outcome: str
    worktree: Path
    events_path: Path


class AgentRuntime:
    """Create isolation, run the SDK loop, and close the factual event stream."""

    def __init__(
        self,
        repository: Path,
        events_path: Path,
        registry_command: tuple[str, ...],
        registry_env: dict[str, str] | None = None,
        runs_root: Path | None = None,
        worktree_manager: CreatesWorktrees | None = None,
        options_builder: OptionsBuilder = build_agent_options,
        sdk_loop: SDKLoop = run_sdk_loop,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.repository = Path(repository).resolve()
        self.events_path = Path(events_path).resolve()
        self.registry_command = registry_command
        self.registry_env = dict(registry_env or {})
        self.worktree_manager = worktree_manager or WorktreeManager(
            repository=self.repository,
            runs_root=runs_root or self.repository / ".kintsugi" / "runs",
        )
        self.options_builder = options_builder
        self.sdk_loop = sdk_loop
        self.clock = clock

    async def execute(self, spec: RunSpec) -> RunOutcome:
        """Execute exactly one Run in a new worktree."""
        worktree = await self.worktree_manager.create(spec.run_id)
        events = EventLog(self.events_path, spec.run_id)
        await events.append(
            "run_started",
            bug_id=spec.bug_id,
            root_cause_class=spec.root_cause_class,
        )

        verifier = VerificationRunner(
            worktree=worktree,
            tests_path=spec.tests_path,
            test_command=spec.test_command,
        )
        hooks = RunHooks(worktree=worktree, events=events)
        runtime_tools = RuntimeTools(
            worktree=worktree,
            events=events,
            verifier=verifier,
        )
        options = self.options_builder(
            worktree=worktree,
            hooks=hooks,
            runtime_tools=runtime_tools,
            registry_command=self.registry_command,
            registry_env=self.registry_env,
            max_turns=spec.max_turns,
            max_budget_usd=spec.max_budget_usd,
            model=spec.model,
        )
        prompt = build_run_prompt(spec)
        started = self.clock()
        try:
            result = await self.sdk_loop(options=options, prompt=prompt)
        except Exception:
            elapsed = max(0.0, self.clock() - started)
            await events.append(
                "run_finished",
                outcome="failed",
                tokens=None,
                cost_usd=None,
                seconds=elapsed,
                sources_count=await events.source_count(),
            )
            raise

        finished = await finish_run(
            events,
            result=result,
            seconds=max(0.0, self.clock() - started),
        )
        return RunOutcome(
            run_id=spec.run_id,
            outcome=str(finished["outcome"]),
            worktree=worktree,
            events_path=self.events_path,
        )


def build_run_prompt(spec: RunSpec) -> str:
    """Tell the agent which Seeded Bug to attempt without giving it the diagnosis."""
    command = " ".join(spec.test_command)
    return f"""\
Attempt Seeded Bug `{spec.bug_id}` in this isolated worktree.

The committed tests are under `{spec.tests_path.as_posix()}`. The runtime's
verify_fix tool will restore that directory and execute:

    {command}

Do not infer a fix from the Root Cause Class stored in run metadata; diagnose
from the test and source in this worktree, then follow the enforced Kintsugi
Run sequence.
"""
