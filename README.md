# Modern Multi-Cloud Data Integration Accelerator

A small, customer-neutral proof of value for bringing synthetic records from two
different platform exports into a governed analytical store. It demonstrates
configurable ingestion, standardization, quality checks, record-level lineage,
role-based dataset access, and shared analytics without requiring cloud
credentials or external services.

## Run it

Requirements: Node.js 20 or later. The accelerator has no third-party
dependencies.

```sh
npm start
npm run query
npm run query -- --role data-steward --dataset lineage
npm test
```

`npm start` reads `config/accelerator.json` and writes JSON datasets under
`build/warehouse/`. The sample inputs are synthetic and live in
`data/sources/platform-a/` (CSV) and `data/sources/platform-b/` (JSON). The
default analyst query exposes only the aggregated `analytics` dataset; a
`data-steward` can also query curated records, lineage, and quality results.

To use another configuration, invoke `node src/cli.js run --config path/to/config.json`
or `node src/cli.js query --config path/to/config.json --role analyst`.
Source file paths and the store path are resolved relative to that configuration.
Each source defines an adapter, path, field map, and optional numeric multiplier.
Metric aliases, region aliases, quality checks, and role-to-dataset grants are
configurable in the JSON file.

## What the proof of value demonstrates

- Modular CSV and JSON file adapters stand in for two independent platform
  extracts; connect organization-approved systems by adding adapters rather than
  changing the normalization and consumption contracts.
- Configurable field mapping, metric/region aliases, and source-level value
  scaling produce a common curated record shape.
- Required-field, ISO-date, numeric, and non-negative checks reject invalid
  records and produce an auditable quality report without copying bad records
  into the curated dataset.
- Lineage associates each curated output record with its source record and
  applied transformations.
- Aggregated analytics provide a shared-consumption dataset with counts, totals,
  and averages. Role policy restricts which datasets the CLI may return.

Read [the architecture](docs/architecture.md) for component boundaries and
security notes, and [the rollout guide](docs/rollout.md) for a practical path
from this bounded demo to a production pilot.
