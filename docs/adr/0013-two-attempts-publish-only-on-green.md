---
status: accepted
---

# Two attempts per Run, and a Skill is published only on passing tests

A Run gets two attempts at a Seeded Bug. A Skill is published only after the test
suite passes. Failed Runs appear in the activity feed but not in the chart.

## Why

Each Research attempt costs minutes under ADR-0005, so a third attempt is mostly
paid for in pre-run waiting time. More usefully, two failures are a signal about
the *bug* rather than an argument for another retry: a Seeded Bug that needs three
attempts is too hard for this demo and should be re-authored under ADR-0004.

Publishing only on green guards the failure mode that could invert the project's
central claim. A Skill with a subtly wrong strategy poisons the Registry: the next
instance of that Root Cause Class takes the Reuse Path, applies the bad strategy,
and fails — so reuse measures *worse* than research, on stage, with no visible
cause.

## Consequences

- **Reuse outcomes are derivable from the existing event log, so no new mechanism
  is needed.** `skill_reused` and `run_finished{outcome}` share a `run_id`, which
  gives success-rate per Skill for free. The Skill card reads "reused 2 times, 2
  succeeded."
- Confidence scores and decay functions are therefore out of scope. A reuse tally
  is also the better artifact: a score invites "where did that number come from?",
  a tally is a fact.
- A poisoned Skill remains possible; this makes it *visible* rather than
  blindsiding. For a twelve-hour build, visible is the right level of ambition.
- Failures stay in the feed because a visible failure is evidence the system is not
  staged. They are excluded from the chart because a failed Run has no meaningful
  duration to compare against its pair.
