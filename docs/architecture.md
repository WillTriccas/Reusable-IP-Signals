# Architecture and evidence model

The CLI (`legacy_accelerator/__main__.py`) accepts a Python file or directory and
writes `assessment.json` and `report.md`. The analyzer parses each `.py` file into
an AST without importing or executing it. It inspects functions and class methods, imports,
local function calls, SQLite use, SQL construction, arithmetic, CSV generation,
dynamic execution, and broad exception handling. Findings include relative file
paths and line numbers. Sorting makes the inventory reproducible.

The recommendation rules are deliberately conservative and ordered: dynamic
execution → **rewrite** candidate; constructed SQL → **refactor** candidate;
local SQLite → **replatform** candidate; non-standard-library import without
higher-priority signal → **rehost** candidate; otherwise **retain** candidate.
These are suggestions for investigation, not automated migration decisions.
Backlog items reference the detected risks and treatment candidates. The phased
plan proposes discovery, stabilization, modernization, and verification; teams
should validate behavior and sequence migrations using the dependency map.

Function names are *inferred* behavior labels, not verified business requirements.
Imports and resolved calls are static dependencies, not proof of runtime usage.
The analyzer does not resolve reflection, dynamic method dispatch, indirect SQL variables,
conditional imports, framework routing, runtime configuration, or data flows.
It does not evaluate performance, security posture, cloud suitability, or complete
business intent. Validate all findings with characterization tests, operational
evidence, and authorized stakeholders before adopting a treatment path.

This repository contains only synthetic source. Do not copy private meetings,
customer identities, proprietary source, confidential architectures, credentials,
or organization-specific configuration into samples, tests, reports, or commits.
