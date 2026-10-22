import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readSource } from "./source-adapters.js";

const DATASETS = new Set(["analytics", "curated", "lineage", "quality"]);

export class AccessDeniedError extends Error {
  constructor(role, dataset) {
    super(`Role "${role}" is not allowed to read the "${dataset}" dataset`);
    this.name = "AccessDeniedError";
  }
}

export async function loadConfig(configPath = defaultConfigPath()) {
  const absolutePath = path.resolve(configPath);
  const config = JSON.parse(await readFile(absolutePath, "utf8"));
  if (!Array.isArray(config.sources) || config.sources.length < 2) {
    throw new Error("Configuration must define at least two sources");
  }
  if (!config.store?.path || !config.access?.roles) {
    throw new Error("Configuration must define a store path and access roles");
  }
  for (const source of config.sources) {
    if (!source.name || !source.path || !source.fields || !["csv", "json"].includes(source.adapter)) {
      throw new Error("Each source must define a name, path, field map, and csv or json adapter");
    }
    if (source.valueMultiplier !== undefined && !Number.isFinite(source.valueMultiplier)) {
      throw new Error(`Source "${source.name}" has an invalid valueMultiplier`);
    }
    for (const field of ["entityId", "date", "metric", "value", "region"]) {
      if (!source.fields[field]) {
        throw new Error(`Source "${source.name}" must map the "${field}" field`);
      }
    }
  }
  return { config, configDirectory: path.dirname(absolutePath) };
}

function normalizeRecord(source, raw, rowNumber, transformations, quality) {
  const recordId = `${source.name}:${rowNumber}`;
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return { failures: ["invalid_record"], recordId };
  }
  const record = {
    entityId: String(raw[source.fields.entityId] ?? "").trim(),
    date: String(raw[source.fields.date] ?? "").trim(),
    metric: String(raw[source.fields.metric] ?? "").trim(),
    value: Number(raw[source.fields.value]),
    region: String(raw[source.fields.region] ?? "").trim(),
    source: source.name,
    sourceRecordId: recordId,
  };
  const failures = [];

  for (const field of ["entityId", "date", "metric", "region"]) {
    if (!record[field]) failures.push(`required_${field}`);
  }
  if (raw[source.fields.value] === undefined || String(raw[source.fields.value]).trim() === "") {
    failures.push("required_value");
  } else if (!Number.isFinite(record.value)) {
    failures.push("numeric_value");
  }
  if (quality.isoDateOnly && record.date && !isIsoDate(record.date)) {
    failures.push("iso_date");
  }
  if (quality.nonNegativeValues && Number.isFinite(record.value) && record.value < 0) {
    failures.push("non_negative_value");
  }

  if (failures.length) {
    return { failures, recordId };
  }

  const appliedTransforms = ["field_mapping"];
  const originalMetric = record.metric;
  record.metric = transformations.metricAliases?.[originalMetric] ?? originalMetric;
  if (record.metric !== originalMetric) {
    appliedTransforms.push("metric_alias");
  }
  const originalRegion = record.region;
  record.region = transformations.regionAliases?.[record.region.toLowerCase()] ?? record.region;
  if (record.region !== originalRegion) {
    appliedTransforms.push("region_alias");
  }
  const multiplier = source.valueMultiplier ?? 1;
  if (multiplier !== 1) {
    record.value *= multiplier;
    if (!Number.isFinite(record.value)) {
      return { failures: ["numeric_value"], recordId };
    }
    appliedTransforms.push("value_multiplier");
  }
  return { record, recordId, appliedTransforms };
}

function isIsoDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(date.valueOf()) && date.toISOString().startsWith(value);
}

function buildAnalytics(records) {
  const totals = new Map();
  for (const record of records) {
    const key = JSON.stringify([record.date, record.metric, record.region]);
    const group = totals.get(key) ?? {
      date: record.date,
      metric: record.metric,
      region: record.region,
      count: 0,
      totalValue: 0,
    };
    group.count += 1;
    group.totalValue += record.value;
    totals.set(key, group);
  }
  return [...totals.values()]
    .map((group) => ({
      ...group,
      totalValue: round(group.totalValue),
      meanValue: round(group.totalValue / group.count),
    }))
    .sort((left, right) =>
      `${left.date}|${left.metric}|${left.region}`.localeCompare(
        `${right.date}|${right.metric}|${right.region}`,
      ),
    );
}

function round(value) {
  return Math.round((value + Number.EPSILON) * 10_000) / 10_000;
}

async function writeDataset(storePath, name, value) {
  await writeFile(path.join(storePath, `${name}.json`), `${JSON.stringify(value, null, 2)}\n`);
}

export async function runPipeline(configPath = defaultConfigPath()) {
  const { config, configDirectory } = await loadConfig(configPath);
  const storePath = path.resolve(configDirectory, config.store.path);
  const curated = [];
  const lineage = [];
  const rejectedRecords = [];
  const sourceSummary = [];

  for (const source of config.sources) {
    const inputRecords = await readSource(source, configDirectory);
    let accepted = 0;
    for (let index = 0; index < inputRecords.length; index += 1) {
      const rowNumber = source.adapter === "csv" ? index + 2 : index + 1;
      const result = normalizeRecord(
        source,
        inputRecords[index],
        rowNumber,
        config.transformations ?? {},
        config.quality ?? {},
      );
      if (result.failures) {
        rejectedRecords.push({
          source: source.name,
          sourceRecordId: result.recordId,
          failedChecks: result.failures,
        });
        continue;
      }
      curated.push(result.record);
      lineage.push({
        outputRecordId: result.record.sourceRecordId,
        source: source.name,
        sourceRecordId: result.record.sourceRecordId,
        transformations: result.appliedTransforms,
      });
      accepted += 1;
    }
    sourceSummary.push({
      source: source.name,
      adapter: source.adapter,
      recordsRead: inputRecords.length,
      recordsAccepted: accepted,
      recordsRejected: inputRecords.length - accepted,
    });
  }

  const qualityReport = {
    recordsRead: sourceSummary.reduce((sum, source) => sum + source.recordsRead, 0),
    recordsAccepted: curated.length,
    recordsRejected: rejectedRecords.length,
    rejectedRecords,
    sources: sourceSummary,
  };
  const analytics = buildAnalytics(curated);

  await mkdir(storePath, { recursive: true });
  await Promise.all([
    writeDataset(storePath, "curated", curated),
    writeDataset(storePath, "analytics", analytics),
    writeDataset(storePath, "lineage", lineage),
    writeDataset(storePath, "quality", qualityReport),
  ]);
  return { storePath, qualityReport, analytics };
}

export async function readDataset(configPath, dataset, role) {
  if (!DATASETS.has(dataset)) {
    throw new Error(`Unknown dataset "${dataset}". Choose: ${[...DATASETS].join(", ")}`);
  }
  const { config, configDirectory } = await loadConfig(configPath);
  const permissions = config.access.roles[role];
  if (!Array.isArray(permissions) || !permissions.includes(dataset)) {
    throw new AccessDeniedError(role, dataset);
  }
  const storePath = path.resolve(configDirectory, config.store.path);
  return JSON.parse(await readFile(path.join(storePath, `${dataset}.json`), "utf8"));
}

function defaultConfigPath() {
  return fileURLToPath(new URL("../config/accelerator.json", import.meta.url));
}
