---
status: superseded
superseded_by: "0014"
---

# Each Run gets a fresh git worktree off a tagged baseline

> **Superseded by [ADR-0014](0014-kintsugi-is-an-mcp-server-not-an-agent.md).**
> Kintsugi no longer creates Run isolation; the host agent owns its workspace.

The sandbox repo is tagged `baseline` at its seeded commit. Every Run is given its
own `git worktree` created from that tag, and works only inside it.

## Why

Six Runs sharing one working copy contaminate each other: leftover edits from one
Run are present in the next, so a fast Reuse-Path Run can no longer be attributed
to the Skill rather than to the previous Run's changes. That destroys the per-pair
comparison ADR-0006 depends on.

Resetting a single copy between Runs (`git reset --hard baseline && git clean -fd`)
was the considered alternative and would have worked, but a worktree per Run keeps
each Run's diff alive in place rather than requiring it to be captured to a patch
file before being destroyed. It also makes "re-run the whole sequence" a matter of
creating fresh trees rather than unwinding state, which matters during repeated dry
runs.

## Consequences

- Each Run's diff remains inspectable after the fact, in its own tree — a useful
  demo artifact: the Skill card shows the pattern, the Run's tree shows the patch
  that pattern produced.
- Untracked files the agent creates cannot leak between Runs, since no tree is
  ever reused. (A reset-based approach would have needed `git clean -fd` for this;
  `git reset --hard` alone leaves untracked files behind.)
- The sandbox must be a real git repo with a `baseline` tag created when the
  Seeded Bugs are authored — before the hackathon, per ADR-0004.
- Runs *could* execute in parallel, but the demo runs them sequentially: the
  narrative is the ordered pairs of ADR-0004, and concurrent agents are not worth
  debugging against a deadline.
