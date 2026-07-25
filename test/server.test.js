import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, test } from "node:test";

import { createEventServer } from "../src/server.js";

const cleanups = [];

afterEach(async () => {
  for (const cleanup of cleanups.splice(0)) {
    await cleanup();
  }
});

async function listenForTest(server) {
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));

  cleanups.push(
    () => new Promise((resolve, reject) => {
      server.close((error) => (error ? reject(error) : resolve()));
    }),
  );

  const { port } = server.address();
  return `http://127.0.0.1:${port}`;
}

async function startServer({ events, skills = [] }) {
  const fixtureDirectory = await mkdtemp(join(tmpdir(), "kintsugi-events-"));
  const eventsPath = join(fixtureDirectory, "events.jsonl");
  const skillsPath = join(fixtureDirectory, "skills");

  await mkdir(skillsPath);
  await writeFile(
    eventsPath,
    `${events.map((event) => JSON.stringify(event)).join("\n")}\n`,
  );

  for (const skill of skills) {
    const skillDirectory = join(skillsPath, skill.id);
    await mkdir(skillDirectory);
    await writeFile(join(skillDirectory, "SKILL.md"), skill.contents);
  }

  const baseUrl = await listenForTest(
    createEventServer({ eventsPath, skillsPath }),
  );
  cleanups.push(() => rm(fixtureDirectory, { recursive: true, force: true }));
  return baseUrl;
}

test("GET /events returns every event in log order", async () => {
  const events = [
    {
      ts: "2026-07-25T10:00:00.000Z",
      run_id: "research-1",
      seq: 1,
      type: "run_started",
    },
    {
      ts: "2026-07-25T10:00:01.000Z",
      run_id: "research-1",
      seq: 2,
      type: "hypothesis_formed",
      text: "A mutable default is shared across calls.",
    },
  ];
  const baseUrl = await startServer({ events });

  const response = await fetch(`${baseUrl}/events`);

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), events);
});

test("GET /skills exposes the content needed for Skill cards", async () => {
  const skills = [
    {
      id: "mutable-defaults",
      contents: `---
name: Repair Mutable Defaults
description: Replace stateful default arguments with per-call values.
aliases:
  - shared default argument
sources:
  - https://docs.python.org/defaults
---

# Repair Mutable Defaults

Mutable defaults keep state between otherwise independent calls.

Use an immutable sentinel and allocate a fresh collection inside the function.
`,
    },
    {
      id: "async-blocking",
      contents: `---
name: Move Blocking Work Off the Event Loop
description: Keep synchronous I/O from blocking asynchronous tasks.
aliases:
  - blocking call in async code
sources:
  - https://docs.python.org/asyncio
---

# Move Blocking Work Off the Event Loop

Blocking I/O stops other asynchronous tasks from making progress.

Move blocking work to a worker thread and await its result.
`,
    },
  ];
  const baseUrl = await startServer({ events: [], skills });

  const response = await fetch(`${baseUrl}/skills`);

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), [
    {
      id: "async-blocking",
      name: "Move Blocking Work Off the Event Loop",
      description: "Keep synchronous I/O from blocking asynchronous tasks.",
      aliases: ["blocking call in async code"],
      sources: ["https://docs.python.org/asyncio"],
      strategy: "Move blocking work to a worker thread and await its result.",
    },
    {
      id: "mutable-defaults",
      name: "Repair Mutable Defaults",
      description: "Replace stateful default arguments with per-call values.",
      aliases: ["shared default argument"],
      sources: ["https://docs.python.org/defaults"],
      strategy:
        "Use an immutable sentinel and allocate a fresh collection inside the function.",
    },
  ]);
});

test("GET /runs projects recorded facts without computing metrics", async () => {
  const events = [
    {
      ts: "2026-07-25T10:00:00.000Z",
      run_id: "research-1",
      seq: 1,
      type: "run_started",
    },
    {
      ts: "2026-07-25T10:00:01.000Z",
      run_id: "research-1",
      seq: 2,
      type: "source_read",
      url: "https://docs.python.org/",
      title: "Python documentation",
    },
    {
      ts: "2026-07-25T10:01:00.000Z",
      run_id: "research-1",
      seq: 10,
      type: "run_finished",
      outcome: "passed",
      tokens: 42000,
      cost_usd: 0.504,
      seconds: 60,
      sources_count: 4,
    },
    {
      ts: "2026-07-25T10:02:00.000Z",
      run_id: "reuse-1",
      seq: 9,
      type: "run_finished",
      outcome: "passed",
      tokens: 9000,
      cost_usd: 0.108,
      seconds: 18,
      sources_count: 0,
    },
  ];
  const baseUrl = await startServer({ events });

  const response = await fetch(`${baseUrl}/runs`);

  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), [
    {
      run_id: "research-1",
      tokens: 42000,
      cost_usd: 0.504,
      seconds: 60,
      sources_count: 4,
      outcome: "passed",
    },
    {
      run_id: "reuse-1",
      tokens: 9000,
      cost_usd: 0.108,
      seconds: 18,
      sources_count: 0,
      outcome: "passed",
    },
  ]);
});

test("GET / serves the dashboard and its local assets", async () => {
  const baseUrl = await startServer({ events: [] });

  const [pageResponse, scriptResponse, stylesResponse] = await Promise.all([
    fetch(`${baseUrl}/`),
    fetch(`${baseUrl}/dashboard.js`),
    fetch(`${baseUrl}/styles.css`),
  ]);
  const page = await pageResponse.text();

  assert.equal(pageResponse.status, 200);
  assert.match(pageResponse.headers.get("content-type"), /^text\/html/);
  assert.match(page, /<main/);
  assert.match(page, /Latest activity/);
  assert.match(page, /Portable Skills/);
  assert.match(page, /Run comparisons/);
  assert.equal(scriptResponse.status, 200);
  assert.match(
    scriptResponse.headers.get("content-type"),
    /^text\/javascript/,
  );
  assert.equal(stylesResponse.status, 200);
  assert.match(stylesResponse.headers.get("content-type"), /^text\/css/);
});

test("bundled fixture contains complete ordered Research and Reuse Path Runs", async () => {
  const fixtureRoot = join(process.cwd(), "fixtures");
  await readFile(join(fixtureRoot, "events.jsonl"), "utf8");
  const server = createEventServer({
    eventsPath: join(fixtureRoot, "events.jsonl"),
    skillsPath: join(fixtureRoot, "skills"),
  });
  const baseUrl = await listenForTest(server);
  const [eventsResponse, skillsResponse] = await Promise.all([
    fetch(`${baseUrl}/events`),
    fetch(`${baseUrl}/skills`),
  ]);
  const events = await eventsResponse.json();
  const skills = await skillsResponse.json();
  const runIds = events
    .filter((event) => event.type === "run_started")
    .map((event) => event.run_id);

  const paths = runIds.map((runId) => {
    const runEvents = events.filter((event) => event.run_id === runId);
    const types = runEvents.map((event) => event.type);
    return {
      run_id: runId,
      decision: runEvents.find((event) => event.type === "registry_queried")
        .decision,
      types,
      hypothesis_before_patch:
        types.indexOf("hypothesis_formed") < types.indexOf("patch_applied"),
      strategy_before_patch:
        types.indexOf("strategy_recorded") < types.indexOf("patch_applied"),
    };
  });

  assert.deepEqual(
    { paths, skills },
    {
      paths: [
        {
          run_id: "research-mutable-default",
          decision: "research",
          types: [
            "run_started",
            "hypothesis_formed",
            "registry_queried",
            "source_read",
            "source_read",
            "strategy_recorded",
            "patch_applied",
            "tests_run",
            "skill_published",
            "run_finished",
          ],
          hypothesis_before_patch: true,
          strategy_before_patch: true,
        },
        {
          run_id: "reuse-mutable-default",
          decision: "reuse",
          types: [
            "run_started",
            "hypothesis_formed",
            "registry_queried",
            "strategy_recorded",
            "skill_reused",
            "patch_applied",
            "tests_run",
            "run_finished",
          ],
          hypothesis_before_patch: true,
          strategy_before_patch: true,
        },
      ],
      skills: [
        {
          id: "async-blocking",
          name: "Move Blocking Work Off the Event Loop",
          description:
            "Keep synchronous I/O from blocking asynchronous tasks.",
          aliases: [
            "blocking call in async code",
            "synchronous work stalls coroutines",
            "event loop blocked by file operation",
          ],
          sources: [
            "https://docs.python.org/3/library/asyncio-task.html#running-in-threads",
          ],
          strategy:
            "Move the blocking operation to a worker thread with the runtime's supported thread bridge, then await its result from the coroutine.",
        },
        {
          id: "mutable-defaults",
          name: "Repair Mutable Defaults",
          description:
            "Replace stateful default arguments with per-call values.",
          aliases: [
            "shared default argument",
            "state leaks between function calls",
            "reused list or dictionary default",
          ],
          sources: [
            "https://docs.python.org/3/tutorial/controlflow.html#default-argument-values",
            "https://docs.python.org/3/reference/compound_stmts.html#function-definitions",
          ],
          strategy:
            "Use an immutable sentinel as the default. Inside the function, allocate a fresh collection whenever the caller did not provide one. Preserve explicitly supplied collections instead of replacing them.",
        },
      ],
    },
  );
});
