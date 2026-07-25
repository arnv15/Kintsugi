function formatDuration(seconds) {
  if (seconds < 60) {
    return `${seconds}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder === 0 ? `${minutes}m` : `${minutes}m ${remainder}s`;
}

function readableName(value) {
  return value.replaceAll("-", " ");
}

function describeEvent(event) {
  switch (event.type) {
    case "run_started":
      return `Started work on ${readableName(event.bug_id)} after identifying the root cause: ${event.root_cause_class}.`;
    case "hypothesis_formed":
      return `Formed a diagnosis: ${event.text}`;
    case "registry_queried":
      return event.decision === "reuse"
        ? "The Skill Registry found a reusable Skill."
        : "No reusable Skill matched, so primary-source research began.";
    case "source_read":
      return `Read “${event.title}” to verify the fix.`;
    case "strategy_recorded":
      return `Chose a fix strategy: ${event.text}`;
    case "patch_applied":
      return `Applied the fix in ${event.files_touched.join(", ")}.`;
    case "tests_run":
      return `Ran the tests: ${event.passed} passed and ${event.failed} failed.`;
    case "skill_published":
      return `Published “${event.name}” as a reusable Skill.`;
    case "skill_reused":
      return `Reused “${event.name}” instead of researching the root cause again.`;
    case "run_finished":
      return event.outcome === "passed"
        ? `Finished successfully in ${formatDuration(event.seconds)}.`
        : `Finished without a verified fix after ${formatDuration(event.seconds)}.`;
    default:
      return `Recorded ${readableName(event.type)}.`;
  }
}

function buildSkillCards(skills, events) {
  const outcomesByRun = new Map(
    events
      .filter((event) => event.type === "run_finished")
      .map((event) => [event.run_id, event.outcome]),
  );

  return skills.map((skill) => {
    const reuses = events.filter(
      (event) =>
        event.type === "skill_reused" && event.skill_id === skill.id,
    );

    return {
      id: skill.id,
      name: skill.name,
      symptom: skill.aliases?.[1] ?? skill.aliases?.[0] ?? skill.description,
      strategy: skill.strategy ?? skill.description,
      sources: skill.sources ?? [],
      reused: reuses.length,
      succeeded: reuses.filter(
        (reuse) => outcomesByRun.get(reuse.run_id) === "passed",
      ).length,
    };
  });
}

function buildComparisons(runs, events) {
  const runDetails = new Map();

  for (const event of events) {
    const details = runDetails.get(event.run_id) ?? {};
    if (event.type === "run_started") {
      details.bugId = event.bug_id;
      details.rootCauseClass = event.root_cause_class;
    }
    if (event.type === "registry_queried") {
      details.path =
        event.decision === "reuse" ? "Reuse Path" : "Research Path";
    }
    runDetails.set(event.run_id, details);
  }

  const grouped = new Map();
  for (const run of runs) {
    const details = runDetails.get(run.run_id);
    if (!details?.rootCauseClass || !details.path) {
      continue;
    }

    const comparison = grouped.get(details.rootCauseClass) ?? {
      rootCauseClass: details.rootCauseClass,
      runs: [],
    };
    comparison.runs.push({
      runId: run.run_id,
      bugId: details.bugId,
      path: details.path,
      metrics: {
        tokens: run.tokens,
        costUsd: run.cost_usd,
        seconds: run.seconds,
        sourcesRead: run.sources_count,
      },
    });
    grouped.set(details.rootCauseClass, comparison);
  }

  return [...grouped.values()].map((comparison) => ({
    ...comparison,
    runs: comparison.runs.sort(
      (left, right) =>
        ["Research Path", "Reuse Path"].indexOf(left.path) -
        ["Research Path", "Reuse Path"].indexOf(right.path),
    ),
  }));
}

export function buildDashboardModel({ events, skills = [], runs = [] }) {
  return {
    activity: events.map((event) => ({
      id: `${event.run_id}:${event.seq}`,
      text: describeEvent(event),
      timestamp: event.ts,
      type: event.type,
    })),
    skills: buildSkillCards(skills, events),
    comparisons: buildComparisons(runs, events),
  };
}

async function readJson(fetcher, path) {
  const response = await fetcher(path);
  if (!response.ok) {
    throw new Error(`Could not load ${path} (${response.status})`);
  }
  return response.json();
}

export async function loadDashboardData(fetcher = fetch) {
  const [events, skills, runs] = await Promise.all([
    readJson(fetcher, "/events"),
    readJson(fetcher, "/skills"),
    readJson(fetcher, "/runs"),
  ]);
  return { events, skills, runs };
}

function element(tagName, className, text) {
  const node = document.createElement(tagName);
  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

function titleCase(value) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function renderSummary(model, runs) {
  const completed = runs.length;
  const succeeded = runs.filter((run) => run.outcome === "passed").length;
  document.querySelector("#run-count").textContent = String(completed);
  document.querySelector("#skill-count").textContent = String(
    model.skills.length,
  );
  document.querySelector("#success-rate").textContent =
    completed === 0 ? "—" : `${Math.round((succeeded / completed) * 100)}%`;
}

function metricDefinitions(run) {
  const { metrics } = run;
  const hasCost = Number.isFinite(metrics.costUsd);
  return [
    {
      label: "Tokens / cost",
      raw: hasCost ? metrics.costUsd : metrics.tokens,
      value: hasCost
        ? `$${metrics.costUsd.toFixed(3)} · ${metrics.tokens.toLocaleString()} tok`
        : `${metrics.tokens.toLocaleString()} tokens`,
    },
    {
      label: "Wall-clock",
      raw: metrics.seconds,
      value: formatDuration(metrics.seconds),
    },
    {
      label: "Sources read",
      raw: metrics.sourcesRead,
      value: `${metrics.sourcesRead} source${metrics.sourcesRead === 1 ? "" : "s"}`,
    },
  ];
}

function renderComparisons(comparisons) {
  const container = document.querySelector("#comparisons");
  container.replaceChildren();

  if (comparisons.length === 0) {
    container.append(
      element(
        "p",
        "empty-copy",
        "Comparisons will appear as soon as a Run finishes.",
      ),
    );
    return;
  }

  for (const comparison of comparisons) {
    const card = element("article", "comparison-card");
    const header = element("header", "comparison-header");
    const headingGroup = element("div");
    headingGroup.append(
      element("h3", "", titleCase(comparison.rootCauseClass)),
    );
    const legend = element("div", "run-legend");
    for (const run of comparison.runs) {
      const item = element(
        "span",
        `legend-item ${run.path === "Reuse Path" ? "reuse" : "research"}`,
      );
      item.append(
        element("span", "legend-swatch"),
        document.createTextNode(
          `${run.path} · ${readableName(run.bugId ?? run.runId)}`,
        ),
      );
      legend.append(item);
    }
    headingGroup.append(legend);
    header.append(
      headingGroup,
      element(
        "span",
        "pair-label",
        comparison.runs.length === 2 ? "Pair complete" : "Pair in progress",
      ),
    );

    const metrics = element("div", "metric-table");
    const definitionsByRun = comparison.runs.map(metricDefinitions);
    for (let metricIndex = 0; metricIndex < 3; metricIndex += 1) {
      const row = element("div", "metric-row");
      const definitions = definitionsByRun.map(
        (definitions) => definitions[metricIndex],
      );
      row.append(element("span", "metric-name", definitions[0].label));
      const bars = element("div", "metric-bars");
      const maximum = Math.max(...definitions.map((metric) => metric.raw), 0);

      definitions.forEach((metric, runIndex) => {
        const run = comparison.runs[runIndex];
        const barRow = element(
          "div",
          `metric-bar-row ${run.path === "Reuse Path" ? "reuse" : "research"}`,
        );
        const track = element("span", "metric-track");
        const fill = element("span", "metric-fill");
        const width = maximum === 0 ? 0 : (metric.raw / maximum) * 100;
        fill.style.setProperty("--bar-width", `${width}%`);
        track.append(fill);
        barRow.append(track, element("span", "metric-value", metric.value));
        bars.append(barRow);
      });
      row.append(bars);
      metrics.append(row);
    }
    card.append(header, metrics);
    container.append(card);
  }
}

function renderSkills(skills) {
  const container = document.querySelector("#skills");
  container.replaceChildren();

  if (skills.length === 0) {
    container.append(
      element("p", "empty-copy", "Published Skills will appear here."),
    );
    return;
  }

  for (const [index, skill] of skills.entries()) {
    const card = element("article", "skill-card");
    const topLine = element("div", "skill-topline");
    topLine.append(
      element("span", "skill-mark", String(index + 1).padStart(2, "0")),
      element(
        "span",
        "tally",
        skill.reused === 0
          ? "Not reused yet"
          : `Reused ${skill.reused} time${skill.reused === 1 ? "" : "s"} · ${skill.succeeded} succeeded`,
      ),
    );
    card.append(topLine, element("h3", "", skill.name));

    const details = element("div", "skill-details");
    const symptom = element("div", "skill-detail");
    symptom.append(
      element("span", "detail-label", "Symptom"),
      element("p", "", skill.symptom),
    );
    const strategy = element("div", "skill-detail");
    strategy.append(
      element("span", "detail-label", "Strategy"),
      element("p", "", skill.strategy),
    );
    details.append(symptom, strategy);
    card.append(details);

    const sources = element("ul", "source-list");
    for (const source of skill.sources) {
      const item = element("li");
      const link = element("a");
      link.href = source;
      link.target = "_blank";
      link.rel = "noreferrer";
      try {
        link.textContent = new URL(source).hostname.replace(/^www\./, "");
      } catch {
        link.textContent = source;
      }
      item.append(link);
      sources.append(item);
    }
    card.append(sources);
    container.append(card);
  }
}

function renderActivity(activity) {
  const container = document.querySelector("#activity");
  container.replaceChildren();

  if (activity.length === 0) {
    container.append(
      element("li", "empty-copy", "The event log is waiting for its first Run."),
    );
    return;
  }

  for (const item of activity) {
    const row = element("li", "activity-item");
    row.dataset.type = item.type;
    const timestamp = new Date(item.timestamp);
    const formattedTime = Number.isNaN(timestamp.valueOf())
      ? "Time unavailable"
      : timestamp.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
    row.append(
      element("span", "activity-marker"),
      element("p", "activity-text", item.text),
      element("time", "activity-time", formattedTime),
    );
    container.append(row);
  }
}

function renderDashboard(data) {
  const model = buildDashboardModel(data);
  renderSummary(model, data.runs);
  renderComparisons(model.comparisons);
  renderSkills(model.skills);
  renderActivity(model.activity);
}

function setStatus(kind, message) {
  const status = document.querySelector("#live-status");
  status.classList.toggle("is-live", kind === "live");
  status.classList.toggle("is-error", kind === "error");
  document.querySelector("#status-text").textContent = message;
}

async function startDashboard() {
  async function refresh() {
    try {
      renderDashboard(await loadDashboardData());
      setStatus("live", "Polling the event log");
      document.querySelector("#last-updated").textContent =
        `Updated ${new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })}`;
    } catch (error) {
      setStatus("error", "Event log unavailable");
      console.error(error);
    } finally {
      window.setTimeout(refresh, 3_000);
    }
  }

  await refresh();
}

if (typeof document !== "undefined") {
  startDashboard();
}
