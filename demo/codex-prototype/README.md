# Codex dashboard demo

A small seeded bug plus a demo `events.jsonl` for dashboard development.

## Files

- `problems/off_by_one/` — a seeded bug (`inventory.py`) with a failing test
  (`test_inventory.py`).
- `generate_demo_run.py` — produces `events.jsonl` for the dashboard.
- `events.jsonl` — the generated event log, schema-valid against
  `kintsugi_agent.events.validate_event`.

## Regenerate the demo run

```bash
agent/.venv/bin/python3 demo/codex-prototype/generate_demo_run.py
```

## View it in the dashboard

```bash
EVENTS_PATH="$PWD/demo/codex-prototype/events.jsonl" \
SKILLS_PATH="$PWD/demo/codex-prototype/skills" \
npm start
```

`/events` and `/runs` both render this file correctly with no dashboard code
changes.

## Wiring Codex to the Registry

MCP is a standard protocol, so the same `kintsugi-registry` server Claude
Code uses works for Codex unchanged. To register it (this edits your global
`~/.codex/config.toml`, so run it yourself rather than scripting it):

```bash
codex mcp add kintsugi-skill-registry \
  --env KINTSUGI_SKILLS_DIR="$PWD/demo/codex-prototype/skills" \
  --env KINTSUGI_SKILLS_REMOTE="" \
  -- "$PWD/registry/.venv/bin/kintsugi-registry"
```
