import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { makePool, makeDb } from "./db.js";
import { handleApi } from "./api.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT ?? 3000);
const db = makeDb(makePool());

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://${req.headers.host ?? "localhost"}`);
  if (url.pathname.startsWith("/api/")) {
    const { status, body } = await handleApi(db, url);
    res.writeHead(status, { "content-type": "application/json; charset=utf-8" });
    res.end(JSON.stringify(body));
    return;
  }
  if (url.pathname === "/" || url.pathname === "/index.html") {
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(await readFile(path.join(here, "..", "public", "index.html")));
    return;
  }
  res.writeHead(404).end("not found");
});

server.listen(PORT, () => console.log(`dashboard on http://localhost:${PORT}`));

for (const sig of ["SIGINT", "SIGTERM"] as const) {
  process.on(sig, async () => {
    server.close();
    await db.close();
    process.exit(0);
  });
}
