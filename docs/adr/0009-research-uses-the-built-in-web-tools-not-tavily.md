---
status: superseded
superseded_by: "0014"
---

# The Research Path uses the SDK's built-in web tools; Tavily is dropped

> **Superseded by [ADR-0014](0014-kintsugi-is-an-mcp-server-not-an-agent.md).**
> Research tooling is now the host agent's concern; Kintsugi supplies no tools.

Research is done with the Claude Agent SDK's built-in `WebSearch` and `WebFetch`
tools. The originally planned Tavily integration is out of scope.

## Why

ADR-0008 brought built-in web search and fetch with it, which made a separate
search provider redundant. Dropping it removes an integration and a dependency
from a twelve-hour build.

The measurement concern that argued for routing research through a single
instrumented door is satisfied anyway: ADR-0008's `PostToolUse` hook fires on
built-in tools too, so every fetch is logged by the same mechanism that logs
everything else. The concern was ever only about having *two* doors — one door is
one door regardless of whose it is.

The cost is one fewer sponsor integration; MCP remains the tie-in that matters,
and ADR-0001 makes it load-bearing rather than decorative.

## Consequences

- **Sources read counts `WebFetch` calls, not `WebSearch` calls.** A search
  returns a list of candidates; only a fetch is a source actually read. Counting
  searches would inflate the number ADR-0006 relies on as its most trustworthy.
- Citations recorded under ADR-0005 are the URLs passed to `WebFetch`, which the
  hook already sees.
