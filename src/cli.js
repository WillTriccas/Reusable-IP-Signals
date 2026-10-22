import { AccessDeniedError, readDataset, runPipeline } from "./pipeline.js";

function parseArguments(args) {
  const [command, ...options] = args;
  const parsed = { command };
  for (let index = 0; index < options.length; index += 1) {
    const option = options[index];
    if (!["--config", "--role", "--dataset"].includes(option) || !options[index + 1]) {
      throw new Error(`Unknown or incomplete option "${option}"`);
    }
    parsed[option.slice(2)] = options[index + 1];
    index += 1;
  }
  return parsed;
}

async function main() {
  try {
    const args = parseArguments(process.argv.slice(2));
    if (args.command === "run") {
      const result = await runPipeline(args.config);
      console.log(
        `Pipeline complete: ${result.qualityReport.recordsAccepted} accepted, ` +
          `${result.qualityReport.recordsRejected} rejected; store: ${result.storePath}`,
      );
      return;
    }
    if (args.command === "query") {
      const dataset = args.dataset ?? "analytics";
      const role = args.role ?? "analyst";
      console.log(JSON.stringify(await readDataset(args.config, dataset, role), null, 2));
      return;
    }
    throw new Error('Usage: node src/cli.js <run|query> [--config path] [--role role] [--dataset name]');
  } catch (error) {
    console.error(error.message);
    process.exitCode = error instanceof AccessDeniedError ? 3 : 1;
  }
}

await main();
