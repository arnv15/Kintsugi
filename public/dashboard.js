const SVG_NAMESPACE = "http://www.w3.org/2000/svg";
const REUSE_TYPES = new Set(["skill_reused", "skill_retrieved"]);
const EVIDENCE_TYPES = new Set([
  "run_started",
  "hypothesis_formed",
  "registry_queried",
  "patch_applied",
  "tests_run",
  "run_finished",
]);

function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) {
    return "—";
  }
  if (seconds < 60) {
    return `${seconds}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder === 0 ? `${minutes}m` : `${minutes}m ${remainder}s`;
}

function readableName(value = "") {
  return value.replaceAll("-", " ");
}

function titleCase(value = "") {
  return readableName(value).replace(/\b\w/g, (letter) =>
    letter.toUpperCase(),
  );
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
      return `Applied the fix in ${(event.files_touched ?? []).join(", ")}.`;
    case "tests_run":
      return `Ran the tests: ${event.passed} passed and ${event.failed} failed.`;
    case "skill_published":
      return `Published “${event.name}” as a reusable Skill.`;
    case "skill_reused":
      return `Reused “${event.name}” instead of researching the root cause again.`;
    case "skill_retrieved":
      return `Took “${event.name}” from the Registry instead of researching the root cause again.`;
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
      (event) => REUSE_TYPES.has(event.type) && event.skill_id === skill.id,
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
    if (run.outcome !== "passed") {
      continue;
    }
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

function buildSummary(runs, events, comparisons) {
  const completed = runs.length;
  const passed = runs.filter((run) => run.outcome === "passed").length;
  const totalTokens = runs.reduce(
    (total, run) => total + (Number.isFinite(run.tokens) ? run.tokens : 0),
    0,
  );
  const totalSeconds = runs.reduce(
    (total, run) => total + (Number.isFinite(run.seconds) ? run.seconds : 0),
    0,
  );
  const avoidedTokens = comparisons.reduce((total, comparison) => {
    const research = comparison.runs.find(
      (run) => run.path === "Research Path",
    );
    const reuse = comparison.runs.find((run) => run.path === "Reuse Path");
    if (
      !Number.isFinite(research?.metrics.tokens) ||
      !Number.isFinite(reuse?.metrics.tokens)
    ) {
      return total;
    }
    return total + Math.max(0, research.metrics.tokens - reuse.metrics.tokens);
  }, 0);

  return {
    completed,
    passed,
    successRate: completed ? Math.round((passed / completed) * 100) : 0,
    totalTokens,
    avoidedTokens,
    averageSeconds: completed ? Math.round(totalSeconds / completed) : 0,
    reuseCount: events.filter((event) => REUSE_TYPES.has(event.type)).length,
  };
}

export function buildDashboardModel({ events, skills = [], runs = [] }) {
  const comparisons = buildComparisons(runs, events);
  return {
    activity: events.map((event) => ({
      id: `${event.run_id}:${event.seq}`,
      text: describeEvent(event),
      timestamp: event.ts,
      type: event.type,
      verified:
        event.type === "run_finished" && event.outcome === "passed",
    })),
    skills: buildSkillCards(skills, events),
    comparisons,
    summary: buildSummary(runs, events, comparisons),
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

function svgElement(tagName, attributes = {}) {
  const node = document.createElementNS(SVG_NAMESPACE, tagName);
  for (const [name, value] of Object.entries(attributes)) {
    node.setAttribute(name, value);
  }
  return node;
}

function setText(selector, value) {
  const node = document.querySelector(selector);
  if (node) {
    node.textContent = value;
  }
}

function renderSummary(summary, skillCount) {
  setText("#run-count", String(summary.completed));
  setText("#skill-count", String(skillCount));
  setText(
    "#success-rate",
    summary.completed === 0 ? "—" : `${summary.successRate}%`,
  );
  setText(
    "#success-detail",
    summary.completed === 0
      ? "waiting for outcomes"
      : `${summary.passed} green outcome${summary.passed === 1 ? "" : "s"}`,
  );
  setText("#tokens-avoided", summary.avoidedTokens.toLocaleString());
  setText("#average-duration", formatDuration(summary.averageSeconds));
  setText("#reuse-count", String(summary.reuseCount));
  setText("#total-tokens", summary.totalTokens.toLocaleString());
}

function renderSeamGraph(activity) {
  const container = document.querySelector("#seam-graph");
  container.replaceChildren();
  const evidence = activity
    .filter((item) => EVIDENCE_TYPES.has(item.type))
    .slice(-10);

  if (evidence.length === 0) {
    container.append(
      element("p", "empty-copy", "The seam is waiting for its first Run."),
    );
    return;
  }

  const width = 900;
  const height = 420;
  const points = evidence.map((item, index) => {
    const x =
      evidence.length === 1
        ? width / 2
        : 70 + index * ((width - 140) / (evidence.length - 1));
    const wave = [0.5, 0.25, 0.66, 0.36, 0.78][index % 5];
    return { item, x, y: 55 + wave * (height - 110) };
  });
  const pathData = points
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`,
    )
    .join(" ");
  const latestFinish = [...evidence]
    .reverse()
    .find((item) => item.type === "run_finished");
  const verified = latestFinish?.verified ?? false;

  const svg = svgElement("svg", {
    viewBox: `0 0 ${width} ${height}`,
    role: "img",
    "aria-label":
      "A gold repair seam connecting the latest recorded Run evidence",
  });
  const defs = svgElement("defs");
  const filter = svgElement("filter", { id: "network-glow" });
  filter.append(
    svgElement("feGaussianBlur", { stdDeviation: "7", result: "blur" }),
  );
  const merge = svgElement("feMerge");
  merge.append(
    svgElement("feMergeNode", { in: "blur" }),
    svgElement("feMergeNode", { in: "SourceGraphic" }),
  );
  filter.append(merge);
  const gradient = svgElement("linearGradient", {
    id: "network-gold",
    x1: "0",
    x2: "1",
  });
  gradient.append(
    svgElement("stop", { "stop-color": "#805821" }),
    svgElement("stop", { offset: ".45", "stop-color": "#f0c872" }),
    svgElement("stop", { offset: "1", "stop-color": "#fff1b6" }),
  );
  defs.append(filter, gradient);
  svg.append(
    defs,
    svgElement("path", { class: "graph-ghost", d: pathData }),
    svgElement("path", {
      class: `graph-seam ${verified ? "is-verified" : "is-pending"}`,
      d: pathData,
    }),
  );

  points.forEach((point, index) => {
    const group = svgElement("g", {
      class: "graph-node",
      transform: `translate(${point.x} ${point.y})`,
    });
    group.style.setProperty("--delay", `${index * 110}ms`);
    group.append(
      svgElement("circle", { class: "node-halo", r: "18" }),
      svgElement("circle", { class: "node-core", r: "5" }),
      svgElement("title"),
    );
    group.querySelector("title").textContent = point.item.text;
    svg.append(group);
  });

  const caption = element("div", "graph-caption");
  const state = element("span");
  state.append(
    element("i", "caption-dot"),
    document.createTextNode(
      verified ? " Latest Run verified" : " Evidence accumulating",
    ),
  );
  caption.append(
    state,
    element(
      "span",
      "",
      `${evidence.length} recent proof point${evidence.length === 1 ? "" : "s"}`,
    ),
  );
  container.append(svg, caption);
}

function metricDefinitions(run) {
  const { metrics } = run;
  const hasCost = Number.isFinite(metrics.costUsd);
  const tokens = Number.isFinite(metrics.tokens) ? metrics.tokens : 0;
  const seconds = Number.isFinite(metrics.seconds) ? metrics.seconds : 0;
  const sources = Number.isFinite(metrics.sourcesRead)
    ? metrics.sourcesRead
    : 0;
  return [
    {
      label: "Tokens / cost",
      raw: hasCost ? metrics.costUsd : tokens,
      value: hasCost
        ? `$${metrics.costUsd.toFixed(3)} · ${tokens.toLocaleString()} tok`
        : `${tokens.toLocaleString()} tokens`,
    },
    {
      label: "Wall-clock",
      raw: seconds,
      value: formatDuration(seconds),
    },
    {
      label: "Sources read",
      raw: sources,
      value: `${sources} source${sources === 1 ? "" : "s"}`,
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
        "A comparison appears when a passing Research or Reuse Run finishes.",
      ),
    );
    return;
  }

  for (const comparison of comparisons) {
    const card = element("article", "comparison-card");
    const header = element("header", "comparison-header");
    const heading = element("div");
    heading.append(
      element("span", "comparison-label", "Root Cause Class"),
      element("h3", "", titleCase(comparison.rootCauseClass)),
    );
    header.append(
      heading,
      element(
        "span",
        "pair-state",
        comparison.runs.length === 2 ? "Pair verified" : "Pair in progress",
      ),
    );

    const legend = element("div", "run-legend");
    for (const run of comparison.runs) {
      const item = element(
        "span",
        `legend-item ${run.path === "Reuse Path" ? "reuse" : "research"}`,
      );
      item.append(
        element("i", "legend-swatch"),
        document.createTextNode(
          `${run.path} · ${readableName(run.bugId ?? run.runId)}`,
        ),
      );
      legend.append(item);
    }

    const table = element("div", "metric-table");
    const definitionsByRun = comparison.runs.map(metricDefinitions);
    for (let metricIndex = 0; metricIndex < 3; metricIndex += 1) {
      const definitions = definitionsByRun.map(
        (definitions) => definitions[metricIndex],
      );
      const maximum = Math.max(
        ...definitions.map((definition) => definition.raw),
        0,
      );
      const row = element("div", "comparison-row");
      row.append(element("span", "metric-name", definitions[0].label));
      const bars = element("div", "metric-bars");

      definitions.forEach((definition, runIndex) => {
        const run = comparison.runs[runIndex];
        const barRow = element(
          "div",
          `metric-bar-row ${run.path === "Reuse Path" ? "reuse" : "research"}`,
        );
        const track = element("span", "metric-track");
        const fill = element("span", "metric-fill");
        fill.style.setProperty(
          "--bar-width",
          `${maximum === 0 ? 0 : (definition.raw / maximum) * 100}%`,
        );
        track.append(fill);
        barRow.append(
          track,
          element("span", "metric-value", definition.value),
        );
        bars.append(barRow);
      });
      row.append(bars);
      table.append(row);
    }
    card.append(header, legend, table);
    container.append(card);
  }
}

function renderSkills(skills) {
  const container = document.querySelector("#skill-grid");
  container.replaceChildren();

  if (skills.length === 0) {
    container.append(
      element("p", "empty-copy dark-copy", "Published Skills will appear here."),
    );
    return;
  }

  skills.forEach((skill, index) => {
    const card = element("article", "cinema-skill");
    card.append(
      element("span", "skill-number", String(index + 1).padStart(2, "0")),
    );

    const titleRow = element("div", "skill-title-row");
    const verificationRate =
      skill.reused === 0 ? 0 : skill.succeeded / skill.reused;
    const verification = element(
      "span",
      "verification-orbit",
      skill.reused === 0 ? "New" : `${skill.succeeded}/${skill.reused}`,
    );
    verification.style.setProperty(
      "--verification-angle",
      `${Math.round(verificationRate * 360)}deg`,
    );
    verification.title =
      skill.reused === 0
        ? "Not reused yet"
        : `${skill.succeeded} of ${skill.reused} reuse Runs verified`;
    titleRow.append(element("h3", "", skill.name), verification);

    const symptom = element("p", "skill-symptom", skill.symptom);
    const strategy = element("p", "skill-strategy", skill.strategy);
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
    const footer = element("footer");
    footer.append(
      element(
        "span",
        "",
        `${skill.reused} reuse${skill.reused === 1 ? "" : "s"}`,
      ),
      element("span", "", `${skill.succeeded} verified`),
    );
    card.append(titleRow, symptom, strategy, sources, footer);
    container.append(card);
  });
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
  renderSummary(model.summary, model.skills.length);
  renderSeamGraph(model.activity);
  renderComparisons(model.comparisons);
  renderSkills(model.skills);
  renderActivity(model.activity);
}

function setStatus(kind, message) {
  const status = document.querySelector("#live-status");
  status.classList.toggle("is-live", kind === "live");
  status.classList.toggle("is-error", kind === "error");
  setText("#status-text", message);
}

function renderInitialError() {
  const messages = [
    ["#seam-graph", "The evidence log is unavailable. Retrying…"],
    ["#comparisons", "Run comparisons are unavailable. Retrying…"],
    ["#skill-grid", "Portable Skills are unavailable. Retrying…"],
    ["#activity", "Event history is unavailable. Retrying…"],
  ];
  for (const [selector, message] of messages) {
    const container = document.querySelector(selector);
    container.replaceChildren(element("p", "empty-copy error-copy", message));
  }
}

async function startDashboard() {
  let lastFingerprint = "";
  let hasRendered = false;

  async function refresh() {
    try {
      const data = await loadDashboardData();
      const fingerprint = JSON.stringify(data);
      if (fingerprint !== lastFingerprint) {
        renderDashboard(data);
        lastFingerprint = fingerprint;
      }
      hasRendered = true;
      setStatus("live", "Live evidence");
      setText(
        "#last-updated",
        `Updated ${new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })}`,
      );
    } catch (error) {
      setStatus("error", "Evidence unavailable");
      if (!hasRendered) {
        renderInitialError();
      }
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
