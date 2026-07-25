---
status: accepted
---

# The agent is the Claude Agent SDK, and hooks are the enforcement mechanism

The agent runs on the Claude Agent SDK (`claude-agent-sdk` / `@anthropic-ai/claude-agent-sdk`)
— Claude Code as a library — rather than a hand-rolled tool-use loop on the plain
Anthropic SDK, or the Claude Code CLI driven headless as a subprocess.

## Why

Read, Write, Edit, Bash, Glob and Grep already exist as built-in tools, so the
build time goes to the Registry and the Seeded Bugs instead of to plumbing. It
also ships a native MCP client, so the Skill Registry of ADR-0001 is consumed as
a genuine MCP server with no client code written.

The decisive reason is that its hooks turn two of our rules from instructions into
mechanisms:

- `PostToolUse` on all tools appends to `events.jsonl`, so the entire event log of
  ADR-0007 is one callback.
- `PreToolUse` matching `Edit|Write` refuses the edit unless a Root Cause
  Hypothesis and a fix strategy have already been recorded. That is ADR-0005's
  ordering rule enforced by the harness rather than requested in a prompt — the
  same style of guard as ADR-0002's leak check and ADR-0003's traceback
  rejection.

And it pays off ADR-0002 in a way that was not anticipated when that decision was
made: the SDK loads skills from `.claude/skills/*/SKILL.md`. A Skill is that
format. So the Reuse Path does not paste a Skill into a prompt — it writes the
Skill's file into `.claude/skills/` and the agent loads it natively. The artifact
is not merely *compatible with* a Claude Code skill; it is one.

## Consequences

- Whether the SDK reports token counts or cost per run was not established when
  this decision was made, and tokens is ADR-0006's headline metric. Verifying it
  is hour-zero work: run one query and inspect the final result message. If the
  field is absent, wall-clock becomes the headline and sources-read carries the
  proof — which is why three metrics were chosen.
- Claude Code's permission model is inherited. `permission_mode` and
  `allowed_tools` must be set deliberately or the agent pauses to ask for
  approval mid-Run.
- The SDK bundles a native binary. Pin the version before the build rather than
  discovering a change mid-demo.
