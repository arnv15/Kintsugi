---
status: accepted
---

# The demo is pre-run, with one live Reuse-Path Run

All six Runs are executed before presenting. The dashboard presents from the
resulting event log. One Run — the second instance of the first Root Cause Class —
is then executed live on stage.

## Why

ADR-0005 makes Research-Path Runs genuinely slow, plausibly minutes each. Six of
them do not fit a demo slot, and each live Run is an opportunity to stall,
rate-limit, or wander in front of an audience.

This works without new machinery because ADR-0007 already put the event log on
disk and had the dashboard derive everything from it. That decision was made for
crash-safety; it happens to make a completed Run indistinguishable from a live one.

The live Run is a Reuse-Path Run rather than a Research-Path one for three
reasons: it is the fast path, so it fits the slot; it is the contested claim, since
nobody doubts an agent can read web pages but everyone doubts the Skill did
anything; and the Registry already holds the Skill published by the recorded
Research Run, so the retrieval is real.

## Consequences

- The Registry needs a way to be cleared or scoped, or the second dry run finds the
  Skill already published and a Research-Path Run can never be demonstrated again.
- A rehearsed fallback is required: if the live Run stalls, its recorded
  counterpart is already in the log. The transition has to be practised — an
  unpractised recovery reads as failure, a practised one reads as preparation.
- Once a good pre-run is captured, the agent is frozen. A late code change that
  invalidates that event log costs the demo.
