import { readFile, readdir } from "node:fs/promises";
import { createServer } from "node:http";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const defaultPublicPath = fileURLToPath(new URL("../public", import.meta.url));
const publicAssets = new Map([
  ["/", ["index.html", "text/html; charset=utf-8"]],
  ["/dashboard.js", ["dashboard.js", "text/javascript; charset=utf-8"]],
  ["/styles.css", ["styles.css", "text/css; charset=utf-8"]],
]);

function sendJson(response, statusCode, value) {
  response.writeHead(statusCode, { "content-type": "application/json" });
  response.end(JSON.stringify(value));
}

async function sendPublicAsset(response, publicPath, asset) {
  const [fileName, contentType] = asset;
  response.writeHead(200, {
    "content-type": contentType,
    "cache-control": "no-cache",
  });
  response.end(await readFile(join(publicPath, fileName)));
}

async function readEvents(eventsPath) {
  const contents = await readFile(eventsPath, "utf8");
  return contents
    .split("\n")
    .filter((line) => line.length > 0)
    .map((line) => JSON.parse(line));
}

function readFrontmatter(contents) {
  return contents.match(/^---\r?\n([\s\S]*?)\r?\n---/)?.[1];
}

function readFrontmatterField(contents, field) {
  const line = readFrontmatter(contents)
    ?.split(/\r?\n/)
    .find((candidate) => candidate.startsWith(`${field}:`));

  return line?.slice(field.length + 1).trim();
}

function readFrontmatterList(contents, field) {
  const frontmatter = readFrontmatter(contents);
  if (!frontmatter) {
    return [];
  }

  const lines = frontmatter.split(/\r?\n/);
  const fieldIndex = lines.findIndex((line) => line === `${field}:`);
  if (fieldIndex === -1) {
    return [];
  }

  const values = [];
  for (const line of lines.slice(fieldIndex + 1)) {
    if (!/^\s+-\s+/.test(line)) {
      break;
    }
    values.push(line.replace(/^\s+-\s+/, ""));
  }
  return values;
}

function readStrategy(contents) {
  const body = contents.replace(/^---\r?\n[\s\S]*?\r?\n---/, "");
  const prose = body
    .replace(/```[\s\S]*?```/g, "")
    .split(/\r?\n\s*\r?\n/)
    .map((paragraph) => paragraph.trim().replace(/\s*\r?\n\s*/g, " "))
    .filter((paragraph) => paragraph && !paragraph.startsWith("#"));

  return prose.at(-1);
}

async function readSkills(skillsPath) {
  const entries = await readdir(skillsPath, { withFileTypes: true });
  const skillIds = entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();

  return Promise.all(
    skillIds.map(async (id) => {
      const contents = await readFile(join(skillsPath, id, "SKILL.md"), "utf8");
      return {
        id,
        name: readFrontmatterField(contents, "name"),
        description: readFrontmatterField(contents, "description"),
        aliases: readFrontmatterList(contents, "aliases"),
        sources: readFrontmatterList(contents, "sources"),
        strategy:
          readStrategy(contents) ?? readFrontmatterField(contents, "description"),
      };
    }),
  );
}

function readRunSummaries(events) {
  return events
    .filter((event) => event.type === "run_finished")
    .map((event) => ({
      run_id: event.run_id,
      tokens: event.tokens,
      cost_usd: event.cost_usd,
      seconds: event.seconds,
      sources_count: event.sources_count,
      outcome: event.outcome,
    }));
}

export function createEventServer({
  eventsPath,
  skillsPath,
  publicPath = defaultPublicPath,
}) {
  return createServer(async (request, response) => {
    const publicAsset = publicAssets.get(request.url);
    if (request.method === "GET" && publicAsset) {
      await sendPublicAsset(response, publicPath, publicAsset);
      return;
    }

    if (request.method === "GET" && request.url === "/events") {
      sendJson(response, 200, await readEvents(eventsPath));
      return;
    }

    if (request.method === "GET" && request.url === "/skills") {
      sendJson(response, 200, await readSkills(skillsPath));
      return;
    }

    if (request.method === "GET" && request.url === "/runs") {
      sendJson(response, 200, readRunSummaries(await readEvents(eventsPath)));
      return;
    }

    sendJson(response, 404, { error: "Not found" });
  });
}
