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
- Source edits require an earlier Root Cause Hypothesis and cited strategy.
- Reuse Path Runs cannot call `WebFetch`.
- Direct Bash verification is denied; `verify_fix` restores committed tests
  immediately before the configured test command.
- Only two verification attempts can execute.
- Only a green Research Path Run may publish a Skill.

## Verify the package

```bash
uv run --project agent pytest
uv run --project agent pyright
```
