---
status: accepted
---

# The agent appends events; the dashboard does the math

The agent keeps a diary: one JSON object per line, appended to `events.jsonl`,
never rewritten. A small HTTP server exposes `/events`, `/skills` and `/runs`, and
the dashboard polls those and derives everything it displays.

## Event types

```
run_started         bug_id, root_cause_class
hypothesis_formed   text
registry_queried    decision: reuse|research, top_score, skill_id
source_read         url, title
strategy_recorded   text, sources: [url]
patch_applied       files_touched
tests_run           passed, failed, output_tail
skill_published     skill_id, name
skill_reused        skill_id, name
run_finished        outcome, tokens, cost_usd, seconds, sources_count
```

Every line carries `ts`, `run_id`, `seq`, `type`.

## Why

This is the contract between two people working in parallel, so it must be
writable before either half exists. Append-only means the two halves cannot break
each other: one writes, one reads, and there is no shared state to corrupt or
migrate mid-build.

Because the log is raw, everything the dashboard needs is derivable from it —
activity feed, reuse counts per Skill, the per-pair chart from ADR-0006 — so the
dashboard never has to ask for a new field.

It also survives the agent dying. The file is on disk, so a crash during the demo
still leaves a dashboard that shows everything that happened.

And it makes ADR-0005's ordering rule directly inspectable: `seq` shows that
`hypothesis_formed` and `strategy_recorded` preceded `patch_applied`.

## Consequences

- **The agent writes facts, never conclusions.** It records `tokens: 40000`; it
  does not record `speedup: 3.2x`. A derived number written by the thing being
  measured is the thing grading its own homework.
- The dashboard carries the reduction logic. That is the right place for it — it is
  the other half of the team, and it is easy work.
- First task of the build, before any agent code: hand-write a fake `events.jsonl`
  covering one Research-Path Run and one Reuse-Path Run, plus two fake Skills, so
  the dashboard can be built immediately against real-shaped data.
