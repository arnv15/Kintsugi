---
status: accepted
---

# Three metrics per Run, compared within a Root Cause Class

Every Run records tokens spent, wall-clock seconds, and sources read. Tokens
(shown as dollars) is the headline number, wall-clock is secondary, and sources
read is the proof.

All three fall out of the same event log, so this is three extra fields rather
than three measurement systems, and they protect each other: if wall-clock looks
bad on one Run because a network call hung, tokens and sources still show the real
shape.

Sources read carries the most weight under scrutiny. It goes from four or five on
the Research Path to zero on the Reuse Path, and unlike time or tokens it cannot
wobble — it is structural, a direct consequence of ADR-0005.

## Consequences

- **Comparisons are made within a Root Cause Class, never across all six Seeded
  Bugs.** The asyncio class is intrinsically harder than the money class, so
  plotting all six Runs in demo order produces a lumpy line that invites the wrong
  question. The chart is three pairs: Research Path versus Reuse Path for each
  class.
- The two instances of a class must therefore be comparable in fix size, even
  though ADR-0004 requires them to look unalike on the surface. If one instance is
  a two-line fix and the other needs thirty, the pair comparison is meaningless.
