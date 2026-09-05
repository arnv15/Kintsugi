---
status: accepted
supersedes: "0008"
---

# Kintsugi is an MCP server; the agent is whatever the user already runs

Kintsugi ships one thing: the Skill Registry as an MCP server. It does not ship
an agent. The bundled Claude Agent SDK runtime — the `agent/` package, its hooks,
its worktrees, and its Run orchestration — is removed. Any MCP-capable coding
agent (Claude Code, Codex, Cursor) connects to the Registry and does the fixing
itself.

This supersedes [ADR-0008](0008-the-agent-is-the-claude-agent-sdk-with-hooks-as-enforcement.md),
and with it the Run-shaped decisions that only described that runtime:
[0009](0009-research-uses-the-built-in-web-tools-not-tavily.md),
[0010](0010-tests-are-restored-from-git-before-verification.md),
[0011](0011-each-run-gets-a-fresh-git-worktree.md),
[0012](0012-the-demo-is-pre-run-with-one-live-reuse-path-run.md) and
[0013](0013-two-attempts-publish-only-on-green.md).

## Why

ADR-0008 was right about what it was optimizing for. Building a controlled
experiment, the SDK's hooks were the cheapest way to turn rules into mechanisms,
and it bought a working agent for free.

But the value being demonstrated was never the agent. It was that a verified fix
can become a portable Skill that a *later, different* agent reuses. Shipping our
own agent asks a user to abandon the one they already have in order to get that
— which is the one thing nobody will do. The Registry has no dependency on the
SDK and never did; it was already the product, sitting inside an experiment.

## Consequences

**The hook-enforced guarantees are gone, and cannot be replaced from here.** A
server can refuse calls made *to it*; it cannot see the host agent's edits, test
runs, or web reads. So these stop being mechanisms:

- publish only after passing tests, with citations observed in that Run
- no source edit before a recorded hypothesis and cited strategy
- tests are immutable, and restored from git before verification
- WebFetch unavailable on the Reuse Path
- two attempts per Run

`publish_skill` is now an honour system, which is the central open problem for a
shared Registry: nothing stops a Skill that was never earned. The two guards
that survive are the ones that live at the Registry's own boundary — the
hypothesis guard of [ADR-0003](0003-skills-are-retrieved-by-root-cause-hypothesis-not-error-text.md)
and the repo-leak guard of [ADR-0002](0002-skills-are-claude-code-skill-documents.md).
Both still hold, unchanged.

**ADR-0002 gets stronger, not weaker.** It anticipated that a Skill *is* a
`.claude/skills/*/SKILL.md`, which was convenient when we controlled the loader.
Now it is the whole distribution story: a user can `git clone` the Skills repo
into `.claude/skills/` and have every Skill natively, with no server at all. The
server earns its place by supplying the `reuse`/`research` decision and the two
guards — not by storing files.

**[ADR-0007](0007-the-agent-writes-an-append-only-event-log-and-computes-nothing.md)
survives with a smaller author.** The split it describes — record facts, reshape
them, conclude separately — is intact, but the Registry is now the only
component present in every Run and so the only honest place to write the log.
It records what it witnesses (`registry_queried`, `skill_retrieved`,
`skill_published`) and nothing else. Token counts, wall-clock, test results and
patches are no longer observable, so they are absent rather than estimated.

**[ADR-0006](0006-three-metrics-compared-within-a-root-cause-class.md)'s
comparison needs a new home.** Comparing a Research Run against a Reuse Run of
the same Root Cause Class depended on matched Seeded Bugs and a runner we
controlled. In the wild there is no counterfactual. The `sandbox/` pair fixtures
are kept for exactly this reason: measurement becomes a periodic evaluation we
run deliberately, not a number the live dashboard can claim.
