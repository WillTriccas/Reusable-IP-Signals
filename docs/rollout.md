# Rollout guide

1. **Bound the pilot.** Select one low-risk analytical question, a small set of
   approved fields, named data owners, and an explicit success measure. Keep
   source extracts synthetic until privacy, security, and access reviews approve
   a controlled real-data pilot.
2. **Map sources.** Add a source entry per platform extract in the accelerator
   configuration. Map fields to the common record shape and confirm date,
   numeric, units, and region semantics with source owners.
3. **Integrate safely.** Implement only the needed adapter behind the
   `readSource` contract. Use managed identity and approved secrets/network
   paths in a real deployment; do not put credentials in configuration or
   source control.
4. **Agree on governance.** Define production roles, least-privilege dataset
   grants, retention, lineage detail, quality thresholds, alert owners, and
   failure/replay expectations. Replace the local demonstration policy with
   enforcement in the trusted query and storage layers.
5. **Run and validate.** Compare source totals with curated and aggregate
   outputs, inspect rejected-record counts, verify lineage, and test allowed
   and denied consumers. Record acceptance criteria and resolve quality
   exceptions with data owners.
6. **Promote in stages.** Deploy to a controlled non-production environment,
   monitor freshness and quality, then expand to additional sources or
   consumers only after the bounded pilot meets its agreed measures. Keep
   configuration, schema changes, and rollback procedures versioned.

The repository's local file adapters, generated samples, and role flag are
intended for demonstrating the pattern. They are not production connectors,
identity controls, or operational service-level guarantees.
