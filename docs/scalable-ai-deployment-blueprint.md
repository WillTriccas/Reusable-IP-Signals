# Scalable AI solution deployment blueprint

This blueprint is a reusable, provider-neutral starting point for moving multiple AI solutions from proof of concept to a governed production platform. The reference implementation is deliberately small and uses only Python's standard library. Its two deterministic workloads return synthetic results; they are demonstrations of deployment boundaries and routing, not real models or production security controls.

## Reference architecture

```text
                             ┌────────────────────────────┐
 Client ── bearer token ───▶│ Shared API gateway          │
                             │ auth · routing · request IDs │
                             └──────────┬─────────┬─────────┘
                                        │         │
                                  /triage/*   /summary/*
                                        │         │
                              ┌─────────▼──┐  ┌───▼────────┐
                              │ triage     │  │ summary    │
                              │ workload   │  │ workload   │
                              │ :8101      │  │ :8102      │
                              └────────────┘  └────────────┘
```

Each workload has its own name, route, process, and port. It can be started or replaced independently. The gateway is a shared entry point and emits request metadata without logging request bodies. `platform.json` is the editable deployment topology; the validator rejects duplicate ports, overlapping routes, unsupported workload kinds, and non-local bind addresses. The local runner starts the same independently addressable services together for convenience.

## Isolation and shared platform boundaries

| Boundary | Local reference | Production pattern |
| --- | --- | --- |
| Workload runtime | Separate process and port per workload | Separate deployment, service account/identity, resource quota, autoscaling policy, and network policy per workload |
| Workload configuration | Name, kind, port, and route in `platform.json` | Versioned configuration per workload and environment; secrets injected from a managed secret store |
| Ingress and identity | Shared gateway with a required bearer token from an environment variable | Managed API gateway; federated workload/user identity, least-privilege authorization, rate limits, and request-size limits |
| Data and model access | No persistence or external model calls | Explicitly scoped storage, model endpoints, encryption, retention, and egress allow-lists per workload |
| Telemetry | Request ID, route, and status only | Shared metrics, traces, and redacted logs with workload/environment dimensions and retention controls |
| Control plane | JSON topology plus validation | Reviewed infrastructure-as-code modules and policy-as-code in the target platform |

The local runner binds only to loopback and does not provide OS/container isolation. Its bearer token is a local demonstration mechanism, not an identity system. Do not expose it to a network or reuse it in production.

## Deployment lifecycle and governance gates

| Stage | Required checks before promotion |
| --- | --- |
| 1. Intake and design | Named owner, intended users, data classification, approved use, workload boundary, dependency/model inventory, and measurable quality and service objectives |
| 2. Build and validate | Reviewed source and configuration, unit and contract tests, dependency and image scans, model/data evaluation, privacy review, resource limits, and reproducible build artifacts |
| 3. Pre-production | Isolated deployment, identity and authorization tests, threat-model review, load/latency and failure tests, monitoring/alert checks, rollback rehearsal, and human review where impacts warrant it |
| 4. Production approval | Explicit risk/governance sign-off, change record, support/on-call ownership, runbook, SLO and alert thresholds, backup/retention plan, and rollback criteria |
| 5. Operate and retire | Monitor quality, drift, cost, security and SLOs; review access and data retention; track incidents and changes; reapprove material model/data changes; revoke access and securely retire resources |

Promotion is a controlled artifact/configuration change, not an automatic consequence of a successful demo. Keep development, test, and production accounts/projects, identities, data, and secrets separate. Record approvals and test results with the versioned release.

## Operational responsibilities

* **Workload team:** owns its model, application, data contracts, evaluation, resource requests, security findings, workload dashboard, service objectives, and runbook.
* **Platform team:** owns gateway, identity integration, network boundaries, deployment templates, CI policy checks, shared observability, quotas, and platform availability.
* **Security/privacy and governance reviewers:** define control requirements and approve data use, risk classification, retention, and production exceptions.
* **Service owner/on-call:** coordinates release readiness, incident response, rollback, communications, post-incident actions, and periodic access/retention reviews.

Assign named teams and escalation paths in each deployment's operational record; these roles are generic and must be mapped to the deploying organization.

## Run the reference locally

Requires Python 3.9 or newer; no package installation is needed.

```sh
cd examples/scalable-ai
python3 app.py validate
export DEMO_API_TOKEN='local-only-change-me'
python3 app.py run
```

In a second terminal, call both independently routed workloads through the shared gateway:

```sh
curl -H "Authorization: Bearer ${DEMO_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"text":"An outage is blocking the release"}' \
  http://127.0.0.1:8080/triage/infer

curl -H "Authorization: Bearer ${DEMO_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"text":"Synthetic first sentence. Synthetic second sentence."}' \
  http://127.0.0.1:8080/summary/infer
```

The response includes the workload name and `synthetic: true`. The first workload classifies synthetic text; the second returns its first sentence. The runner can be stopped with Ctrl+C. To change ports, routes, host bindings, or workload kinds, edit `platform.json` and run `python3 app.py validate` again. For fully independent local deployment, run `python3 app.py workload triage` and `python3 app.py workload summary` in separate terminals, then run `python3 app.py gateway`; set `DEMO_API_TOKEN` in the gateway environment.

## Production deployment guidance

The local program is an executable reference for service boundaries, not cloud infrastructure. Implement the production pattern with the deploying platform's reviewed, parameterized infrastructure modules or manifests. Keep workload deployments independently versioned, and use a shared gateway and observability layer without sharing workload secrets or data by default.

Before production:

1. Replace the synthetic handlers with a versioned model-serving or inference adapter and document model provenance, evaluation results, and rollback compatibility.
2. Build immutable, scanned workload images; deploy each in a separate namespace or equivalent security boundary with non-root execution, read-only filesystems where possible, CPU/memory/GPU limits, and autoscaling bounds.
3. Replace the demo token with managed identity and short-lived credentials; enforce authorization per route, TLS, network policies, egress restrictions, secret rotation, and audit logging.
4. Parameterize environment-specific hostnames, replicas, resource requests, model references, data locations, retention, and SLO/alert thresholds. Never commit credentials or customer data in configuration.
5. Promote the same signed artifact through isolated environments only after the lifecycle gates above pass. Use health/readiness checks, progressive rollout, rollback automation, and an owner-approved change record.
6. Validate backup/recovery, capacity and cost limits, model/data lifecycle, incident response, and decommissioning before accepting production traffic.

## Validation

From the repository root:

```sh
python3 examples/scalable-ai/app.py validate
python3 -m unittest discover -s tests -v
```

The tests check topology isolation invariants and exercise both workloads through a live local gateway, including rejection of unauthenticated requests.
