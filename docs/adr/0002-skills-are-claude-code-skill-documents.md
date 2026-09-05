---
status: accepted
---

# Skills are Claude Code `SKILL.md` documents, guarded against repo leakage

A Skill is a Markdown document in Claude Code's own skill format — YAML
frontmatter with `name` and `description`, then a prose body — rather than a
bespoke JSON schema of our own design. This makes every Skill directly
installable by any Claude Code instance, so ADR-0001's second consumer is a file
copy rather than a custom client. It also means `search_skills` matches against
`description`, a field whose existing purpose is precisely to decide whether a
skill applies.

The body describes a Root Cause Class in prose and **may** include a short
illustrative before/after snippet, because models apply a pattern far more
reliably from one worked example than from a paragraph describing it.

## Considered options

A stored patch or templated diff was rejected: it is reusable only when the next
bug is a copy of the last one, and it makes the system a cache rather than a
learning system. An executable codemod was rejected as a 12-hour trap — the
generalization logic is harder to author than the agent loop, and it only covers
narrowly syntactic defects.

Prose-only (no snippet) was rejected because abstract Skills degrade into advice
the model already has unprompted, which flattens the speedup the project exists
to demonstrate.

## Consequences

- Permitting snippets reopens the cache risk, since the cheapest way to write an
  illustration is to paste the real diff and rename the variables. So
  `publish_skill` **mechanically rejects** any Skill whose code blocks appear as
  a substring of the sandbox repo (whitespace-normalized, blocks over two lines
  only). A rejection is retried with feedback, never a hard failure.
- The guard is a claim we can state as checkable rather than promised: Skills are
  *prevented* from carrying code out of the repo they were learned in.
- This format choice turned out to be worth more than portability alone. Claude
  Code and every agent that follows its convention load skills from
  `.claude/skills/*/SKILL.md`, so a retrieved Skill is *installed as a file* and
  loaded natively rather than pasted into a prompt. Under
  [ADR-0014](0014-kintsugi-is-an-mcp-server-not-an-agent.md) this became the
  distribution story outright: the Skills repo clones straight into
  `.claude/skills/` and works with no server running.
- The fast path stays genuinely fast but is not instant — roughly a few times
  faster, not orders of magnitude, because the agent must still locate the defect
  and write the patch itself. Demo narration must not promise "near-instant".
