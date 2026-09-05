---
status: superseded
superseded_by: "0014"
---

# Tests are restored from git before every verification run

> **Superseded by [ADR-0014](0014-kintsugi-is-an-mcp-server-not-an-agent.md).**
> Kintsugi no longer runs verification, so it cannot restore tests before one.

`git checkout -- tests/` runs immediately before the test command that decides
whether a Seeded Bug is fixed. The tests a fix is judged against are therefore
always the ones authored into the repo, never a version the agent touched.

A `PreToolUse` hook matching `Edit|Write` additionally denies any path under
`tests/`, returning a reason the agent can act on.

## Why

"The tests failed, then they passed" is the definition of fixed, the gate on
publishing a Skill, and the basis of every number in ADR-0006. There are two ways
to make a failing test pass: fix the defect, or change the test — and changing the
test is the cheaper route whenever the real fix is hard. A model takes that route
occasionally, not adversarially but as the path of least resistance. Once, unnoticed,
is enough to publish a Skill for a bug that was never fixed and invalidate the
measurements.

The restore is the load-bearing guard because it closes routes we did not
enumerate: the hook sees `Edit` and `Write`, but the agent also has `Bash`, and
`sed -i` or `rm` against a test file never reaches the hook. The hook is worth
keeping anyway — it is a few lines inside a callback ADR-0008 already requires, and
a denial with a reason ("fix the source, not the test") redirects the agent, where
a silent restore just makes its work appear not to have happened.

## Consequences

- A denied test write is a signal about the Seeded Bug, not about the hook. If a
  bug's fix genuinely requires changing its test, that bug is mis-authored under
  ADR-0004 and should be rewritten.
- The sandbox must be a real git repository with the tests committed before any
  Run starts.
