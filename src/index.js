import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { createEventServer } from "./server.js";

const projectRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const host = process.env.HOST ?? "127.0.0.1";
const port = Number.parseInt(process.env.PORT ?? "3000", 10);

const server = createEventServer({
  eventsPath:
    process.env.EVENTS_PATH ?? resolve(projectRoot, "fixtures/events.jsonl"),
  skillsPath:
    process.env.SKILLS_PATH ?? resolve(projectRoot, "fixtures/skills"),
});

server.listen(port, host, () => {
  console.log(`Kintsugi event server listening at http://${host}:${port}`);
});
