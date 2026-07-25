---
status: accepted
---

# Seeded Bugs must be documented library pitfalls, two instances per Root Cause Class

The sandbox repo carries six Seeded Bugs: three Root Cause Classes, two instances
each. A bug is only eligible if it satisfies two constraints that rule out most of
the bugs one would naturally reach for.

**It must be a pitfall the web has documented.** Application-logic defects
("the discount should apply before tax") are unresearchable — no external source
knows the business rules — so the Research Path would return nothing useful and
the research integration would be decoration.

**It must not be something the model already knows cold.** A mutable default
argument appears in every Python tutorial and gets one-shot without research or
Skill, which would make the Research Path no slower than the Reuse Path and
flatten the very measurement the project exists to produce. Eligible pitfalls are
therefore mostly *library and version semantics* rather than language trivia —
well documented precisely because they are confusing.

## The classes

| Root Cause Class | Instance 1 | Instance 2 |
|---|---|---|
| DST-boundary datetime arithmetic | `scheduling.py::next_run_at` — `timedelta(hours=24)` used to mean "tomorrow, same time" | `reports.py::shift_duration` — subtracting aware datetimes across the transition reports 8h for a 9h shift |
| Money held as float instead of Decimal | `checkout.py::total_with_tax` — accumulation error, total off by a cent | `payouts.py::split_evenly` — three-way split of `100.00` does not sum back to `100.00` |
| `asyncio` exception semantics | `fetcher.py::fetch_all` — `gather` swallows a failure and returns partial results as complete | `writer.py::flush` — coroutine never awaited, writes silently lost |

`pandas` chained assignment / `SettingWithCopy` was the strongest alternate, its
appeal being that the correct fix depends on the installed version, which makes
research unusually load-bearing.

## Why this shape

Two instances rather than three: a third instance of a class proves nothing the
second didn't, at the same authoring cost as a whole new class. Three classes
rather than one: the "getting faster" claim needs three Research-Path runs and
three Reuse-Path runs to read as a trend instead of an anecdote.

The two instances of a class must differ in file, function, symptom, types, and
test shape while sharing the fix strategy. If they resemble each other, a
sceptical observer assumes a planted copy; when they look unrelated and the
Registry still matches them, the retrieval is visibly doing real work. This only
functions because of ADR-0003 — the two Root Cause Hypotheses match each other
even though the two bugs do not.

## Consequences

- Authoring the sandbox repo is pre-hackathon work, not an opening-hour task. Each
  bug needs enough surrounding code that the defect is not sitting alone under a
  spotlight, plus a test that fails for the right reason.
- Demo order is adjacent pairs — A1, A2, B1, B2, C1, C2 — so the
  research-then-reuse contrast lands three times consecutively rather than
  requiring the audience to remember run #1 by the time run #4 arrives.
