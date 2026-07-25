import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildDashboardModel,
  loadDashboardData,
} from "../public/dashboard.js";

test("activity feed describes every event in log order for a non-technical viewer", () => {
  const events = [
    {
      ts: "2026-07-25T16:00:00.000Z",
      run_id: "research-1",
      seq: 1,
      type: "run_started",
      bug_id: "inventory-history",
      root_cause_class: "mutable default argument",
    },
    {
      ts: "2026-07-25T16:00:08.000Z",
      run_id: "research-1",
      seq: 2,
      type: "hypothesis_formed",
      text: "State from one result is leaking into the next.",
    },
    {
      ts: "2026-07-25T16:00:12.000Z",
      run_id: "research-1",
      seq: 3,
      type: "registry_queried",
      decision: "research",
      top_score: 0.31,
      skill_id: null,
    },
    {
      ts: "2026-07-25T16:00:29.000Z",
      run_id: "research-1",
      seq: 4,
      type: "source_read",
      title: "Python documentation",
      url: "https://docs.python.org/",
    },
    {
      ts: "2026-07-25T16:01:18.000Z",
      run_id: "research-1",
      seq: 5,
      type: "patch_applied",
      files_touched: ["inventory/history.py"],
    },
    {
      ts: "2026-07-25T16:01:31.000Z",
      run_id: "research-1",
      seq: 6,
      type: "tests_run",
      passed: 18,
      failed: 0,
    },
    {
      ts: "2026-07-25T16:01:45.000Z",
      run_id: "research-1",
      seq: 7,
      type: "run_finished",
      outcome: "passed",
      seconds: 105,
    },
  ];

  const model = buildDashboardModel({ events, skills: [], runs: [] });

  assert.deepEqual(
    model.activity.map((item) => item.text),
    [
      "Started work on inventory history after identifying the root cause: mutable default argument.",
      "Formed a diagnosis: State from one result is leaking into the next.",
      "No reusable Skill matched, so primary-source research began.",
      "Read “Python documentation” to verify the fix.",
      "Applied the fix in inventory/history.py.",
      "Ran the tests: 18 passed and 0 failed.",
      "Finished successfully in 1m 45s.",
    ],
  );
});

test("Skill cards derive reuse results by joining events on run_id", () => {
  const skills = [
    {
      id: "mutable-defaults",
      name: "Repair Mutable Defaults",
      description: "Replace stateful default arguments with per-call values.",
      aliases: [
        "mutable default argument",
        "state leaks between function calls",
      ],
      sources: [
        "https://docs.python.org/3/tutorial/controlflow.html#default-argument-values",
      ],
      strategy:
        "Use an immutable sentinel and allocate a fresh collection for each omitted argument.",
      reuse_tally: { reused: 99, succeeded: 99 },
    },
  ];
  const events = [
    {
      run_id: "reuse-passed",
      seq: 5,
      type: "skill_reused",
      skill_id: "mutable-defaults",
    },
    {
      run_id: "reuse-passed",
      seq: 8,
      type: "run_finished",
      outcome: "passed",
    },
    {
      run_id: "reuse-failed",
      seq: 5,
      type: "skill_reused",
      skill_id: "mutable-defaults",
    },
    {
      run_id: "reuse-failed",
      seq: 8,
      type: "run_finished",
      outcome: "failed",
    },
    {
      run_id: "research-passed",
      seq: 10,
      type: "run_finished",
      outcome: "passed",
    },
  ];

  const model = buildDashboardModel({ events, skills, runs: [] });

  assert.deepEqual(model.skills, [
    {
      id: "mutable-defaults",
      name: "Repair Mutable Defaults",
      symptom: "state leaks between function calls",
      strategy:
        "Use an immutable sentinel and allocate a fresh collection for each omitted argument.",
      sources: [
        "https://docs.python.org/3/tutorial/controlflow.html#default-argument-values",
      ],
      reused: 2,
      succeeded: 1,
    },
  ]);
});

test("chart comparisons pair Research and Reuse Runs within each Root Cause Class", () => {
  const definitions = [
    ["research-mutable", "inventory-history", "mutable default argument", "research"],
    ["reuse-mutable", "report-buckets", "mutable default argument", "reuse"],
    ["research-async", "image-loader", "blocking call in async code", "research"],
    ["reuse-async", "audit-writer", "blocking call in async code", "reuse"],
    ["research-money", "invoice-total", "binary float for money", "research"],
    ["reuse-money", "refund-total", "binary float for money", "reuse"],
  ];
  const events = definitions.flatMap(
    ([run_id, bug_id, root_cause_class, decision]) => [
      {
        run_id,
        seq: 1,
        type: "run_started",
        bug_id,
        root_cause_class,
      },
      { run_id, seq: 2, type: "registry_queried", decision },
    ],
  );
  const runs = definitions.map(([run_id], index) => ({
    run_id,
    tokens: 40_000 - index * 5_000,
    cost_usd: 0.48 - index * 0.06,
    seconds: 100 - index * 10,
    sources_count: index % 2 === 0 ? 4 : 0,
    outcome: "passed",
  }));

  const model = buildDashboardModel({ events, skills: [], runs });

  assert.deepEqual(
    model.comparisons.map((comparison) => ({
      rootCauseClass: comparison.rootCauseClass,
      paths: comparison.runs.map((run) => run.path),
      runIds: comparison.runs.map((run) => run.runId),
    })),
    [
      {
        rootCauseClass: "mutable default argument",
        paths: ["Research Path", "Reuse Path"],
        runIds: ["research-mutable", "reuse-mutable"],
      },
      {
        rootCauseClass: "blocking call in async code",
        paths: ["Research Path", "Reuse Path"],
        runIds: ["research-async", "reuse-async"],
      },
      {
        rootCauseClass: "binary float for money",
        paths: ["Research Path", "Reuse Path"],
        runIds: ["research-money", "reuse-money"],
      },
    ],
  );
  assert.deepEqual(model.comparisons[0].runs[0].metrics, {
    tokens: 40_000,
    costUsd: 0.48,
    seconds: 100,
    sourcesRead: 4,
  });
});

test("failed Runs with unavailable SDK metrics are excluded from comparisons", () => {
  const model = buildDashboardModel({
    events: [
      {
        run_id: "failed-research",
        seq: 1,
        type: "run_started",
        bug_id: "scheduling",
        root_cause_class: "DST-boundary datetime arithmetic",
      },
      {
        run_id: "failed-research",
        seq: 2,
        type: "registry_queried",
        decision: "research",
      },
    ],
    skills: [],
    runs: [
      {
        run_id: "failed-research",
        tokens: null,
        cost_usd: null,
        seconds: 3,
        sources_count: 0,
        outcome: "failed",
      },
    ],
  });

  assert.deepEqual(model.comparisons, []);
});

test("dashboard loads all three fixture endpoints", async () => {
  const requested = [];
  const responses = {
    "/events": [{ run_id: "run-1", seq: 1, type: "run_started" }],
    "/skills": [{ id: "skill-1", name: "A Skill" }],
    "/runs": [{ run_id: "run-1", outcome: "passed" }],
  };
  const fetcher = async (path) => {
    requested.push(path);
    return {
      ok: true,
      json: async () => responses[path],
    };
  };

  const result = await loadDashboardData(fetcher);

  assert.deepEqual(requested.sort(), ["/events", "/runs", "/skills"]);
  assert.deepEqual(result, {
    events: responses["/events"],
    skills: responses["/skills"],
    runs: responses["/runs"],
  });
});
