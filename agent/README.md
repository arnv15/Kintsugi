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
uv run --project agent kintsugi-agent-live-pair
```

It first fixes `scheduling` on the Research Path and publishes the learned
Skill to a new local Registry. It then fixes the paired `reports` bug in another
baseline worktree and fails unless that Run reuses the published Skill, reads
zero web sources, and passes. Artifacts are retained under
`.kintsugi/live-pairs/<pair-id>/`; use `--pair-id` to name a rehearsal.
