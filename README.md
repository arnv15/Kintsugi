# Kintsugi

Kintsugi is an autonomous bug-fixing agent that turns each fix into a portable
Skill that future agents can reuse.

## Event fixture server

The repository includes a hand-written event log with one complete Research Path
Run and one complete Reuse Path Run, plus two fake Skills. Start its read-only
HTTP server with:

```sh
npm start
```

The server listens on `127.0.0.1:3000` and exposes:

- `GET /events` — every JSONL event as JSON, in file order
- `GET /skills` — each Skill's directory ID, name, and description
- `GET /runs` — the recorded `run_id`, `tokens`, `seconds`, `sources_count`, and
  `outcome` fields from each `run_finished` event

Set `EVENTS_PATH`, `SKILLS_PATH`, `HOST`, or `PORT` to read a different log or
Skill directory or to change the listening address. The server reads the files
on every request and does not calculate derived metrics.
