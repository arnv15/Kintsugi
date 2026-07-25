# Kintsugi

Kintsugi is an autonomous bug-fixing agent that turns each fix it makes into a
portable Skill, published to a shared Skill Registry — so any agent later facing
a bug of the same Root Cause Class reuses the reasoning instead of rediscovering
it.

## Language

**Root Cause Class**:
A kind of programming mistake, independent of where it appears or how it
surfaces — for example, a mutable object used as a default parameter value. It
is the unit a fix strategy can attach to.
_Avoid_: bug type, error type, bug category, error class

**Seeded Bug**:
A defect deliberately authored into the sandbox repo, together with the test that
catches it. Two Seeded Bugs of the same Root Cause Class are deliberately unalike
on the surface.
_Avoid_: planted bug, fixture bug, test case

**Skill**:
A portable, installable document describing exactly one Root Cause Class and how
bugs of that class are fixed. Never carries code from the repo it was learned in.
_Avoid_: recipe, playbook, pattern, fix template, patch

**Skill Registry**:
The shared store of Skills, reachable by any agent over MCP.
_Avoid_: skill server, skill library, cache, skill database

**Root Cause Hypothesis**:
One sentence of the agent's own diagnosis, naming in prose the Root Cause Class
it believes it is looking at. The only thing the Skill Registry accepts as a
query.
_Avoid_: error signature, search term, query string

**Run**:
One attempt by the agent at one Seeded Bug, from first reading the failing test to
a verified fix or a give-up. The unit everything is measured per.
_Avoid_: session, job, task, episode

**Reuse Path**:
The route taken when the Registry finds a Skill for the Root Cause Hypothesis:
the agent adopts the Skill's fix strategy instead of researching one.
_Avoid_: fast path, hit, cache hit, warm path

**Research Path**:
The route taken when the Registry finds no Skill: the agent researches the Root
Cause Class from primary sources, synthesizes a fix strategy, and publishes a new
Skill on success.
_Avoid_: slow path, cold path, miss, cache miss
