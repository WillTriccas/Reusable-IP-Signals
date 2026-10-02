import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
const publicDirectory = resolve(root, "public");
const sourceDirectory = resolve(root, "src");
const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
};

const server = createServer(async (request, response) => {
  if (request.method !== "GET") {
    response.writeHead(405, { Allow: "GET" }).end("Method not allowed");
    return;
  }

  let pathname;
  try {
    pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
  } catch {
    response.writeHead(400).end("Bad request");
    return;
  }

  const servingSource = pathname.startsWith("/src/");
  const baseDirectory = servingSource ? sourceDirectory : publicDirectory;
  const relativePath = pathname === "/"
    ? "index.html"
    : servingSource ? pathname.slice("/src/".length) : pathname.slice(1);
  const filePath = resolve(baseDirectory, relativePath);
  if (!filePath.startsWith(`${baseDirectory}${sep}`)) {
    response.writeHead(404).end("Not found");
    return;
  }

  try {
    const content = await readFile(filePath);
    response.writeHead(200, {
      "Content-Type": contentTypes[extname(filePath)] ?? "application/octet-stream",
      "X-Content-Type-Options": "nosniff",
      "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'",
    }).end(content);
  } catch {
    response.writeHead(404).end("Not found");
  }
});

const port = Number(process.env.PORT ?? 4173);
server.listen(port, "127.0.0.1", () => {
  console.log(`Agent control plane listening at http://127.0.0.1:${port}`);
});
