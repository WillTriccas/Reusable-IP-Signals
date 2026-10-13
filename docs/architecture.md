# Architecture and operating guide

## Flow

`src/cli.js` reads a JSON capability profile and invokes the dependency-free policy functions in `src/assessment.js`. The assessment evaluates the profile against the timestamp supplied by `--now` (or the current time), identifies unmet controls, and maps each gap to a pattern in `CONTROL_PATTERNS`.

With `--demo`, the workflow clones the input profile, applies restrictive defaults, and consumes only explicit ownership acceptance, attestation, access-review decisions, and exception approval evidence included in the profile. Each action appends a sequence-numbered, timestamped event with an actor and target. The output contains initial and final assessments as well as the effective profile and audit trail. No external system is called and no input file is modified.

## Profile and configuration

Use `examples/synthetic-profile.json` as a schema-by-example. Profiles are JSON objects with:

| Field | Purpose |
| --- | --- |
| `id`, `name` | Stable capability identifier and display name. |
| `dataClassification` | Descriptive labels for the capability's data; the prototype does not infer authorization from them. |
| `policy` | Explicit `externalSharing` and `providerTraining` booleans; absent or enabled values are gaps and the demo turns both off. |
| `owner` | Current owner `id` and ISO `expiresAt`. A renewal requires an explicit `workflow.ownershipAcceptance` with `ownerId` and future `expiresAt`. |
| `attestation` | Current `status: "attested"`, non-empty `reviewer` and `statement`, and ISO `attestedAt`. Optional `maxAgeDays` defaults to 365. |
| `accessReview` | Non-empty `reviewer`, ISO `reviewedAt`, and a decision for each member. Optional `maxAgeDays` defaults to 90. Decisions are `retain` or `revoke`. |
| `exception` | Optional request with `status: "pending"`, `controlId`, non-empty `rationale`, `requestedBy`, and future ISO `expiresAt`. |
| `workflow` | Explicit synthetic actions consumed by demo mode: `ownershipAcceptance`, `attestation`, `accessReview`, and `exceptionApproval`. Missing or incomplete decisions do not create evidence. |

Assessment gaps map to the technology-neutral entries in `CONTROL_PATTERNS`, which describe the blocker, implementation pattern, and expected evidence. Cadences can be tailored with `attestation.maxAgeDays` and `accessReview.maxAgeDays`. Restrictive defaults remain disabled unless an exception process separately approves a bounded deviation.

Exceptions are reported separately from control gaps and never remove the underlying gap. A pending or invalid exception produces an exception-handling gap. The demo records the request and only completes it when the profile supplies a distinct approver, a non-empty approval rationale, an approval timestamp that is not in the future, and an unexpired request. Self-approval is rejected. This is a synthetic workflow demonstration, not an authorization service.

## Audit and limitations

The in-memory audit trail is ordered and useful for demonstrating evidence shape; it is not tamper-proof or durable. A production adaptation should persist events to a protected audit store, authenticate actors, validate the profile against organization policy, enforce access changes at the target platform, and alert or block operation on expiry. The prototype does not connect to AI services, classify real data, validate identities, or claim regulatory compliance.

All bundled names, records, rationales, dates, and classifications are synthetic. Do not replace these fixtures with private meeting material, customer identities, or organization-specific configuration.
