# Kintsugi agent runtime

The runtime attempts one Seeded Bug with the pinned Claude Agent SDK, connects
to the Skill Registry over MCP, and writes the accepted append-only event
contract to a real `events.jsonl`.

## Run one Seeded Bug

Install the package and its pinned dependencies:

```bash
uv sync --project agent
```

Set up Claude Code authentication (`ANTHROPIC_API_KEY` or an authenticated
Claude Code installation), then run:

A Claude Team seat works here when Claude Code is signed in with SSO via
`claude auth login --claudeai --sso`; `claude auth status` should report
`loggedIn: true` before you start a paid Run.

```bash
uv run --project agent kintsugi-agent \
  --run-id scheduling-research \
  --bug-id scheduling \
  --root-cause-class "DST-boundary datetime arithmetic" \
  --test-command "python3 -m unittest sandbox.tests.test_scheduling -v"
```

The command creates `.kintsugi/runs/scheduling-research` as a detached worktree
from the immutable `baseline` tag. It retains that worktree for inspection and
appends Run events to `events.jsonl`.

The default Registry command is:

```bash
uv run --project registry kintsugi-registry
```

Use `--skills-dir` for a local/rehearsal store or `--skills-remote` for the
shared git-backed store. `KINTSUGI_SKILLS_DIR` and
`KINTSUGI_SKILLS_REMOTE` are also honored.

## Enforced Run rules

- `Edit` and `Write` cannot target any `tests/` path or leave the worktree.
- Source edits require an earlier Root Cause Hypothesis and cited strategy whose
  URLs were observed in that Run.
- `WebFetch` is unavailable until the Registry selects the Research Path and
  remains unavailable throughout a Reuse Path Run.
- Direct Bash verification is denied; `verify_fix` restores committed tests
  immediately before the configured test command.
- The SDK loop stops after the second failed verification attempt.
- Any source edit after a green verification invalidates that result.
- Bash is closed after green verification so the verified state cannot change.
- Only a currently green Research Path Run may publish a Skill, and every
  published citation must have been read during that Run.

## Verify the package

```bash
uv run --project agent pytest
uv run --project agent pyright
```

## Run the paid live acceptance pair

The normal suite does not invoke a model or spend tokens. After configuring
Claude Code authentication, this explicit command exercises the real SDK,
Registry MCP server, hooks, and two fresh worktrees:

```bash
uv run --project agent kintsugi-agent-live-pair \
  --model claude-sonnet-4-6 \
  --max-budget-usd 2.00
```

It first fixes `scheduling` on the Research Path and publishes the learned
Skill to a new local Registry. It then fixes the paired `reports` bug in another
baseline worktree and fails unless that Run reuses the published Skill, reads
zero web sources, and passes. Artifacts are retained under
`.kintsugi/live-pairs/<pair-id>/`; use `--pair-id` to name a rehearsal.

`--model` defaults to the same `claude-sonnet-4-6` the six-Run capture pins, so
a rehearsal predicts the capture's token and wall-clock behaviour. Unlike the
capture command, `--max-budget-usd` is optional here and omitting it leaves the
Run uncapped; pass it explicitly when rehearsing. Note that this command
validates the Research-to-Reuse mechanism only — the strict token and
wall-clock comparisons are enforced by `kintsugi-agent-live-demo`, so read
`run_finished` in the retained log to inspect a rehearsal's margins.

## Capture the paid six-Run demo

Issue #7 has a separate opt-in command that pins the model, requires an explicit
per-Run API budget, creates a new local Registry, and executes the Seeded Bugs
sequentially in the exact order A1 → A2 → B1 → B2 → C1 → C2:

```bash
agent/.venv/bin/kintsugi-agent-live-demo \
  --capture-id issue-7 \
  --model claude-sonnet-4-6 \
  --max-turns 40 \
  --max-budget-usd 2.00
```

The command refuses to reuse any existing capture output. It retains six fresh
baseline worktrees under `.kintsugi/live-demos/issue-7/runs/`, writes the real
append-only log to `demo/issue-7/events.jsonl`, stores the three published
Skills under `demo/issue-7/skills/`, and fails unless every pair proves lower
tokens, lower wall-clock time, and zero sources read on the Reuse Path.

Point the unchanged event server and dashboard at that capture with:

```bash
EVENTS_PATH="$PWD/demo/issue-7/events.jsonl" \
SKILLS_PATH="$PWD/demo/issue-7/skills" \
npm start
```

## Rehearse cold to warm repeatedly

The issue #8 rehearsal script gives the pair a stable, resettable Registry scope
and a fresh artifact directory on every invocation:

```bash
scripts/rehearse_cold_warm.sh
```

It resets only
`.kintsugi/rehearsals/dst-cold-warm/skills`, aborts before the second Run unless
the `scheduling` Run proves the Research Path and publishes a Skill, and then
fails unless paired bug `reports` proves the Reuse Path with zero
`source_read` events. Every invocation gets a timestamp-plus-random attempt ID,
so earlier worktrees and event proof remain inspectable and no manual cleanup
is required. The pair explicitly disables `KINTSUGI_SKILLS_REMOTE`, so an
ambient shared-Registry configuration cannot refill the empty rehearsal scope.

Use `--scope` to name a separate rehearsal Registry or `--attempt-id` to give
one attempt a predictable artifact name:

```bash
scripts/rehearse_cold_warm.sh --scope stage --attempt-id dress-rehearsal-1
```
