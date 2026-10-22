# Architecture

## Data flow

```text
Synthetic platform-A CSV ─┐
                          ├─> source adapters ─> field mapping and transforms
Synthetic platform-B JSON ┘                    ─> quality gate
                                                   ├─> curated.json
                                                   ├─> lineage.json
                                                   ├─> quality.json
                                                   └─> analytics.json
                                                        └─> role-checked CLI
```

The default proof of value is local and deterministic for fixed inputs and
configuration. It has no cloud SDK, network connection, or credentials. CSV and
JSON adapters are modular examples of platform-export integration patterns,
not live connectors to a named cloud provider. The `readSource` adapter
contract in `src/source-adapters.js` is the extension point for approved
connectors.

## Components and contracts

- `config/accelerator.json` selects two sources, maps their fields, configures
  standardization and quality rules, points at the analytical store, and grants
  dataset access to roles.
- `src/source-adapters.js` reads configured CSV or JSON files into arrays of
  source records.
- `src/pipeline.js` validates configuration, standardizes records, rejects
  failed quality checks, records lineage, aggregates accepted records, and
  writes four JSON datasets to the store.
- `src/cli.js` runs the pipeline or returns a dataset after checking the
  configured role grant.

The curated schema is `entityId`, `date`, `metric`, `value`, `region`, `source`,
and `sourceRecordId`. Analytics are grouped by date, metric, and region and
contain `count`, `totalValue`, and `meanValue`. Lineage stores source record
identifiers and transformation names. Quality results include source counts
and failed check names, not rejected source payloads.

## Governance and production boundary

The role argument demonstrates policy wiring only; it is not authentication.
Anyone able to run this local CLI can choose a configured role. The generated
JSON files are not encrypted, access-controlled storage. A production
implementation must integrate trusted identity, authorization enforcement at
the storage/query layer, secret management, encryption, retention, audit
logging, and deployment-specific network controls. Validate applicable privacy,
security, and data residency requirements before using real data.
