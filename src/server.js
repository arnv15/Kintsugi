import { readFile, readdir } from "node:fs/promises";
import { createServer } from "node:http";
import { join } from "node:path";

function sendJson(response, statusCode, value) {
  response.writeHead(statusCode, { "content-type": "application/json" });
  response.end(JSON.stringify(value));
}

async function readEvents(eventsPath) {
  const contents = await readFile(eventsPath, "utf8");
  return contents
    .split("\n")
    .filter((line) => line.length > 0)
    .map((line) => JSON.parse(line));
}

function readFrontmatterField(contents, field) {
  const frontmatter = contents.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  const line = frontmatter?.[1]
    .split(/\r?\n/)
    .find((candidate) => candidate.startsWith(`${field}:`));

  return line?.slice(field.length + 1).trim();
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
      seconds: event.seconds,
      sources_count: event.sources_count,
      outcome: event.outcome,
    }));
}

export function createEventServer({ eventsPath, skillsPath }) {
  return createServer(async (request, response) => {
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
