# Regulated AI compensating-controls accelerator

A customer-neutral, dependency-free prototype for assessing synthetic AI capability profiles, mapping governance gaps to reusable control patterns, and recording compensating-control evidence. It is a reference implementation, not a compliance certification or production control plane.

## Requirements and setup

- Node.js 20 or newer
- No third-party packages

```sh
npm test
npm start
npm start -- --demo
```

The default profile is `examples/synthetic-profile.json`. To assess another JSON profile:

```sh
npm start -- ./path/to/profile.json
npm start -- --demo ./path/to/profile.json --now 2026-10-13T12:00:00Z
```

The regular assessment reports gaps and matched patterns. `--demo` additionally executes only the explicit synthetic workflow decisions in the profile and returns the initial assessment, effective profile, final assessment, and ordered audit trail. A fixed `--now` timestamp makes results reproducible.

## What is included

- Restrictive defaults for external sharing and provider use for training.
- Lifecycle owner acceptance, expiry detection, and renewal evidence.
- Attributable, dated governance attestation.
- Per-principal access retain/revoke recertification.
- Time-bounded, attributable approved exceptions that preserve the underlying residual gap.
- A technology-neutral pattern library, synthetic example, and core behavior tests.

See [the architecture and profile guide](docs/architecture.md) for profile fields, decisions, extension points, and limitations.
