# Kintsugi

Kintsugi is a **Skill Registry that any coding agent can connect to over MCP**.
When an agent verifies a bug fix, it publishes the reusable reasoning as a
portable Skill. The next agent to hit the same *kind* of mistake — in a
different repo, on a different machine, running a different product — reuses
that Skill instead of rediscovering it.

The unit is the **Root Cause Class**: a kind of programming mistake, independent
of where it appears or how it surfaces. Two bugs of the same class look nothing
alike on the surface, which is why the Registry matches on your diagnosis rather
than on your error text.

Kintsugi does not ship an agent. Bring your own — Claude Code, Codex, Cursor, or
anything else that speaks MCP.

## Connect it

```json
{
  "mcpServers": {
    "kintsugi-skill-registry": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/arnv15/Kintsugi#subdirectory=registry",
        "kintsugi-registry"
      ],
      "env": {
        "KINTSUGI_SKILLS_REMOTE": "https://github.com/arnv15/kintsugi-skills.git"
      }
    }
  }
}
```

That is the whole installation. The first run clones the shared Skills repo into
`~/.kintsugi/skills`.

See [`registry/README.md`](registry/README.md) for configuration, the four
tools, the guards, and how to run it from a local checkout.

## What your agent does with it

1. It hits a bug and **diagnoses it** — one sentence naming the kind of mistake.
2. It sends that sentence to `search_skills`. A traceback, file path or line
   number is **refused**, so diagnosis cannot be skipped.
3. The Registry answers `reuse` or `research`.
   - **Reuse** — `get_skill` returns a complete `SKILL.md`. Write it to
     `.claude/skills/<id>/SKILL.md` and your agent loads it natively.
   - **Research** — no Skill exists; your agent reads primary sources.
4. Once the fix passes, it calls `publish_skill`. Any code block that appears
   verbatim in your repo is **refused** — a Skill has to teach the class to an
   agent working on a repo it has never seen.

## You do not strictly need the server

A Skill is a plain `SKILL.md`, so the shared store is directly installable:

```sh
git clone https://github.com/arnv15/kintsugi-skills .claude/skills/kintsugi
```

Run the server when you want the parts a folder cannot give you: the
`reuse`/`research` decision, and the two guards.

## Dashboard

A read-only HTTP server exposes the event log and Skills; a browser dashboard
derives the activity feed and Skill reuse tallies from them. Neither computes
anything the Registry did not record.

```sh
npm start
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). Endpoints:

- `GET /events` — every JSONL event as JSON, in file order
- `GET /skills` — each Skill's directory ID and display content
- `GET /runs` — the recorded metrics from each `run_finished` event

It reads [`fixtures/events.jsonl`](fixtures/events.jsonl) by default. To watch
your own agents instead, point the Registry at a log and the server at the same
file:

```sh
export KINTSUGI_EVENTS_PATH="$PWD/events.jsonl"   # in the MCP server's env
EVENTS_PATH="$PWD/events.jsonl" SKILLS_PATH="$HOME/.kintsugi/skills" npm start
```

`EVENTS_PATH`, `SKILLS_PATH`, `HOST` and `PORT` all override the defaults.

## Evaluating whether reuse actually helps

[`sandbox/`](sandbox/README.md) holds six Seeded Bugs — three Root Cause Classes,
two deliberately dissimilar instances each — frozen at the `baseline` tag. They
exist so the reuse claim can be measured on demand rather than asserted:

```sh
python3 scripts/verify_sandbox.py
```

These are evaluation fixtures, not part of the shipped tool.

## Repository layout

| Path | What it is |
| --- | --- |
| `registry/` | The Skill Registry MCP server — the product |
| `src/`, `public/`, `test/` | Read-only event server and dashboard |
| `sandbox/`, `scripts/` | Seeded Bug evaluation fixtures and their verifier |
| `fixtures/` | Example event log and Skills for the dashboard |
| `docs/` | Architecture pages and Architecture Decision Records |

## Design

Start with [`CONTEXT.md`](CONTEXT.md) for the vocabulary, then
[`docs/architecture/`](docs/architecture/README.md) for the map. The decisions
behind it — including
[ADR-0014](docs/adr/0014-kintsugi-is-an-mcp-server-not-an-agent.md), which
removed the bundled agent — are in [`docs/adr/`](docs/adr/).
