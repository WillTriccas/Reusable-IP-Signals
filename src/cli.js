#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { assessCapability, CONTROL_PATTERNS, runControlWorkflow } from "./assessment.js";

const defaultProfile = fileURLToPath(new URL("../examples/synthetic-profile.json", import.meta.url));

async function main() {
  const args = process.argv.slice(2);
  let demo = false;
  let profilePath;
  let now = new Date();
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === "--demo") {
      demo = true;
    } else if (args[index] === "--now") {
      if (!args[index + 1]) throw new Error("--now requires an ISO date.");
      now = new Date(args[index + 1]);
      index += 1;
    } else if (args[index].startsWith("--")) {
      throw new Error(`Unknown option: ${args[index]}`);
    } else if (profilePath) {
      throw new Error("Provide only one capability profile path.");
    } else {
      profilePath = args[index];
    }
  }
  if (Number.isNaN(now.getTime())) throw new Error("--now must be a valid ISO date.");

  const profile = JSON.parse(await readFile(resolve(profilePath ?? defaultProfile), "utf8"));
  const result = demo
    ? runControlWorkflow(profile, { now })
    : { assessment: assessCapability(profile, { now }) };
  process.stdout.write(`${JSON.stringify({ ...result, controlLibrary: CONTROL_PATTERNS }, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
});
