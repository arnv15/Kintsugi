# Kintsugi

Kintsugi is an autonomous bug-fixing agent that turns each fix into a portable
Skill that future agents can reuse.

## Dashboard and event fixture server

The repository includes a hand-written event log with one complete Research Path
Run and one complete Reuse Path Run, plus two fake Skills. Start the read-only
HTTP server and dashboard with:

```sh
npm start
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000) to view the dashboard. It
polls the fixture endpoints every three seconds and derives the activity feed,
Skill reuse tallies, and Root Cause Class pair comparisons in the browser.

The server exposes:

- `GET /events` — every JSONL event as JSON, in file order
- `GET /skills` — each Skill's directory ID and display content
- `GET /runs` — the recorded `run_id`, `tokens`, `cost_usd`, `seconds`,
  `sources_count`, and `outcome` fields from each `run_finished` event

Set `EVENTS_PATH`, `SKILLS_PATH`, `HOST`, or `PORT` to read a different log or
Skill directory or to change the listening address. The server reads the files
on every request and does not calculate derived metrics; all joins and
comparisons stay in the dashboard.

## Agent runtime

The `agent/` package runs one Seeded Bug in a fresh detached worktree from the
`baseline` tag. It uses the pinned Claude Agent SDK, connects to the Skill
Registry over MCP, enforces test and citation policy with hooks, restores tests
before verification, and appends the real Run to `events.jsonl`.

See [`agent/README.md`](agent/README.md) for the command and configuration.
