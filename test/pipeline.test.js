import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { AccessDeniedError, readDataset, runPipeline } from "../src/pipeline.js";

async function makeFixture(t, { invalid = false } = {}) {
  const directory = await mkdtemp(path.join(os.tmpdir(), "integration-accelerator-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  await mkdir(path.join(directory, "sources", "a"), { recursive: true });
  await mkdir(path.join(directory, "sources", "b"), { recursive: true });
  await writeFile(
    path.join(directory, "sources", "a", "usage.csv"),
    [
      "workspace,day,metric,units,market",
      "synthetic-1,2026-02-01,users,4,north-america",
      ...(invalid ? ["synthetic-2,not-a-date,users,-2,emea"] : []),
      "",
    ].join("\n"),
  );
  await writeFile(
    path.join(directory, "sources", "b", "costs.json"),
    JSON.stringify([
      {
        project: "synthetic-3",
        day: "2026-02-01",
        metric: "spend",
        amount: 12.5,
        market: "na",
      },
      ...(invalid ? [null] : []),
    ]),
  );
  const configPath = path.join(directory, "config.json");
  await writeFile(
    configPath,
    JSON.stringify({
      sources: [
        {
          name: "source-a",
          adapter: "csv",
          path: "sources/a/usage.csv",
          fields: {
            entityId: "workspace",
            date: "day",
            metric: "metric",
            value: "units",
            region: "market",
          },
        },
        {
          name: "source-b",
          adapter: "json",
          path: "sources/b/costs.json",
          fields: {
            entityId: "project",
            date: "day",
            metric: "metric",
            value: "amount",
            region: "market",
          },
        },
      ],
      transformations: {
        metricAliases: { users: "active_users", spend: "cloud_spend" },
        regionAliases: { "north-america": "NA", na: "NA" },
      },
      quality: { isoDateOnly: true, nonNegativeValues: true },
      store: { path: "warehouse" },
      access: {
        roles: {
          analyst: ["analytics"],
          "data-steward": ["analytics", "curated", "lineage", "quality"],
        },
      },
    }),
  );
  return configPath;
}

test("ingests two adapters, transforms records, and publishes shared aggregates", async (t) => {
  const configPath = await makeFixture(t);
  const result = await runPipeline(configPath);
  const curated = await readDataset(configPath, "curated", "data-steward");
  const analytics = await readDataset(configPath, "analytics", "analyst");
  const lineage = await readDataset(configPath, "lineage", "data-steward");

  assert.equal(result.qualityReport.recordsAccepted, 2);
  assert.deepEqual(
    curated.map(({ metric, region }) => [metric, region]),
    [["active_users", "NA"], ["cloud_spend", "NA"]],
  );
  assert.equal(analytics.length, 2);
  assert.ok(lineage.every((entry) => entry.transformations.includes("field_mapping")));
  assert.ok(lineage.every((entry) => entry.transformations.includes("metric_alias")));
  assert.ok(lineage.every((entry) => entry.transformations.includes("region_alias")));
  assert.ok(lineage.some((entry) => entry.source === "source-a"));
  assert.ok(lineage.some((entry) => entry.source === "source-b"));
  assert.equal(
    JSON.parse(await readFile(path.join(result.storePath, "quality.json"), "utf8")).recordsRejected,
    0,
  );
});

test("reports invalid records and excludes them from the curated store", async (t) => {
  const configPath = await makeFixture(t, { invalid: true });
  const result = await runPipeline(configPath);
  const curated = await readDataset(configPath, "curated", "data-steward");
  const quality = await readDataset(configPath, "quality", "data-steward");

  assert.equal(result.qualityReport.recordsRejected, 2);
  assert.equal(curated.length, 2);
  assert.deepEqual(quality.rejectedRecords[0].failedChecks, [
    "iso_date",
    "non_negative_value",
  ]);
  assert.deepEqual(quality.rejectedRecords[1].failedChecks, ["invalid_record"]);
});

test("enforces configured dataset permissions", async (t) => {
  const configPath = await makeFixture(t);
  await runPipeline(configPath);

  await assert.rejects(
    readDataset(configPath, "curated", "analyst"),
    AccessDeniedError,
  );
  await assert.rejects(
    readDataset(configPath, "analytics", "unknown-role"),
    AccessDeniedError,
  );
  assert.equal((await readDataset(configPath, "analytics", "analyst")).length, 2);
});
