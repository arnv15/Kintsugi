---
status: accepted
---

# No fix may be applied without a citation

The agent is never allowed to fix a bug from memory. Before it edits code it must
have a cited justification for its fix strategy. On the Research Path that
citation is earned from primary sources. On the Reuse Path the Skill *is* the
citation, because it already carries the sources gathered when its Root Cause
Class was first researched.

Research once, cite forever.

## Why

Without this rule the model is free to one-shot any Seeded Bug it happens to
recognise. The Research Path would then cost almost nothing, the Reuse Path would
save almost nothing, and the speedup the project exists to demonstrate would
depend on the model happening not to know things — a bet that is lost invisibly,
one bug at a time.

The rule makes the saving structural rather than circumstantial: the Research
Path pays a cost that cannot be skipped, and reuse is the only way to satisfy the
same requirement without paying it twice.

It also holds up under challenge, which a deliberate handicap would not. This is
the policy one would actually want in production — an autonomous agent should not
guess at library or version semantics from memory. Research is how it earns a
citation the first time; a Skill is how it inherits one.

## Consequences

- Skills carry a `sources` field, which makes them auditable rather than merely
  asserted, and reinforces the provenance consequence in ADR-0001.
- The agent could turn evidence into ceremony: patch from memory, then find a page
  that agrees and cite it afterwards. In the log that is indistinguishable from
  free choice. So the Root Cause Hypothesis and the fix strategy must be recorded
  **before** any edit tool is called, and the sequence is logged. The ordering in
  the event log is the proof, and it costs nothing, since that log is already
  being written for the dashboard.
- Research Path runs become genuinely slow, plausibly minutes each. Six bugs at
  that pace will not fit inside a live demo slot, so how the demo is staged
  becomes a real question.
