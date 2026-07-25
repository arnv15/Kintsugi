---
status: accepted
---

# Skills are retrieved by root-cause hypothesis, and the Registry decides the match

`search_skills` takes one sentence of the agent's own diagnosis — *"a mutable
list is used as a default argument, so it persists across calls"* — never the
exception text or stack trace. Matching is fuzzy (`rapidfuzz.token_set_ratio`)
against each Skill's `description` and its `aliases`, scored server-side against
a threshold, and the **Registry** returns the verdict.

## Why not search on the error signature

The demo depends on the second bug of a Root Cause Class looking nothing like the
first — different file, different types, different symptom, often no exception at
all. That makes surface text worthless as a retrieval key: string similarity
finds surface resemblance, and we deliberately engineered the surface to differ.

The problem was never the matcher, it was the query. Skill descriptions are prose
about root causes; once the query is also prose about a root cause, both sides of
the comparison live in the same vocabulary space and fuzzy matching works well.
Semantic search over embeddings was therefore dropped from scope entirely rather
than kept as a stretch goal — it solves a problem this reframing removes.

`aliases` (3–5 synonymous phrasings, written by the publishing agent) carry more
weight than they appear to: `token_set_ratio` is unforgiving about vocabulary, so
"function remembers values from a previous call" and "state persists across
calls" score poorly against each other despite meaning the same thing. Each alias
is another shot on goal, and it buys most of what embeddings would have.

## Why the Registry decides, and not the agent

The alternative is the agent reading `list_skills` and announcing that it
recognizes a pattern. That is a self-report from the component with an incentive
to look good, and it is unfalsifiable — there is no way to distinguish genuine
retrieval from the model simply already knowing the fix. With the decision in the
Registry, the speedup metric originates in a component with no stake in the
outcome, and "the Registry scored it 84 against a threshold of 70" is a fact
rather than a claim.

## Consequences

- The verdict is named `reuse` / `research`, never `hit` / `miss`. Hit and miss
  are cache vocabulary — the precise words a sceptical listener reaches for — and
  shipping them in the tool contract, the event log, and the dashboard would hand
  over the framing for free. `reuse` / `research` names what happens next rather
  than whether a lookup succeeded, which is also the more accurate description of
  the branch. The two routes are correspondingly the Reuse Path and the Research
  Path, not fast and cold.
- A forced diagnosis step precedes every lookup, on both paths. Diagnosis is
  therefore never part of the saving; what a Skill saves is research and strategy
  synthesis only.
- `search_skills` rejects a query containing `Traceback`, a file path, or a line
  number, mechanically enforcing "diagnose before you look up" — the same style of
  guard as ADR-0002's leak check.
- A misdiagnosis yields a confident match on the wrong Root Cause Class. Tests
  catch it, but it burns one of a bounded number of attempts.
