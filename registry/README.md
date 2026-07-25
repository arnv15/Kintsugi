# Skill Registry

The shared store of Skills, reachable by any agent over MCP (ADR-0001). Storage
is a directory of `<skill-id>/SKILL.md` folders — there is no database, and the
document the Registry serves is the same document an agent installs (ADR-0002).

## Running it

```bash
uv run --directory registry kintsugi-registry
```

It speaks MCP over stdio. Two environment variables configure it:

| Variable | Meaning |
| --- | --- |
| `KINTSUGI_SKILLS_DIR` | Where Skills are stored. Defaults to `~/.kintsugi/skills` — a user-level path, not a repo-level one, because the Registry is shared across repos and machines. |
| `KINTSUGI_SANDBOX_REPO` | The repo Skills are being learned in. Set it and the repo-leak guard runs on every publish, whether or not the caller passes `repo_path`. |

To register it with a Claude Agent SDK client or a Claude Code instance:

```json
{
  "mcpServers": {
    "kintsugi-skill-registry": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/Kintsugi/registry", "kintsugi-registry"],
      "env": {
        "KINTSUGI_SKILLS_DIR": "/absolute/path/to/skills",
        "KINTSUGI_SANDBOX_REPO": "/absolute/path/to/sandbox-repo"
      }
    }
  }
}
```

## Tools

| Tool | Purpose |
| --- | --- |
| `search_skills(hypothesis)` | Returns `decision: "reuse"` with matches, or `decision: "research"` |
| `get_skill(skill_id)` | One Skill in full, including an installable `SKILL.md` in `document` |
| `list_skills()` | Every Skill, without bodies |
| `publish_skill(...)` | Adds a Skill, or refuses it with `feedback` to act on |

Three rules are mechanisms here rather than instructions:

- **`search_skills` takes a Root Cause Hypothesis and nothing else.** A query
  carrying a traceback, a file path or a line number is refused *before* any
  matching runs, so an agent cannot skip diagnosis and search on error text
  (ADR-0003). The refusal is an error, not a `research` decision — a caller told
  to research would simply research, and the guard would have enforced nothing.
- **The decision is the Registry's.** `search_skills` returns matches at or above
  the score threshold and nothing below it, so there is nothing for a caller to
  argue with. Matching is `rapidfuzz.token_set_ratio` against each
  Skill's `description` and its `aliases`, best score per Skill.
- **A Skill cannot carry code out of the repo it was learned in.** At publish
  time, any fenced code block over two lines that appears — whitespace-normalized
  — anywhere under the repo is refused, naming the colliding file and asking for
  a synthetic rewrite (ADR-0002). The repo comes from `repo_path` or from
  `KINTSUGI_SANDBOX_REPO`, so the guard does not depend on the agent it
  constrains passing an argument. With neither set, the result reports
  `leak_check: "skipped"` rather than silently passing; a repo that is named but
  unreadable is an error, so a wrong path cannot become a quiet way through.

`publish_skill` refuses only for the leak guard and for missing `name`,
`description` or `body`. Everything else that weakens a Skill — fewer than three
aliases, no `sources`, no `published_by` — comes back as `warnings` on a
successful publish, because refusing a sound Skill mid-Run is worse than storing
a thin one.

## Resetting between rehearsals

Clearing is an operator action, deliberately absent from the MCP tool surface —
a Run has no reason to empty the shared Registry.

```bash
uv run --directory registry kintsugi-registry-admin clear --yes
```

`list` shows what is stored; `--dry-run` shows what `clear` would remove;
without `--yes`, `clear` refuses and exits non-zero. All three accept
`--skills-dir` to act on a directory other than the default.

## Tests

```bash
uv run --directory registry pytest
```

Tests work at the Registry's tool boundary — the same four operations exposed
over MCP — plus one pass through a real MCP client session, and none of them
assert on how the matcher is implemented. Two reach past that boundary on
purpose: the ordering proof for the hypothesis guard (a claim about sequence
cannot be observed from output alone) and the safety test for `clear` (which has
to look at the directory, because deleting from it is the behaviour under test).
