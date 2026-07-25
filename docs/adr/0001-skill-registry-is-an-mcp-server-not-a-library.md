---
status: accepted
---

# The Skill Registry is an MCP server consumed by any agent, not an internal library

Kintsugi's agent both writes and reads Skills, so the Registry could have been a
local module the agent imports. We made it an MCP server instead, and we treat
"any agent, on any machine, working on any repo" as the consumer. MCP is
therefore load-bearing: it is the wire protocol that makes cross-agent reuse
possible at all, rather than an integration we added on top of a library call.

## Consequences

- Skills must be repo-agnostic. A Skill that only makes sense inside the
  sandbox repo is worthless to the second consumer, so this decision is what
  forces the discipline recorded in ADR-0002.
- Skills carry provenance (which agent published them), because "who learned
  this" is meaningful once there is more than one publisher.
- A second-client demo — a separate Claude Code session, on a different repo,
  solving a bug with a Skill our agent wrote — is possible but not committed to.
