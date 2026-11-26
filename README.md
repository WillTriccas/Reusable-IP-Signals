# Secure AI-Ready Developer Workspace Blueprint

A customer-neutral reference blueprint for developer workspaces that combine capable local development with governed cloud and short-lived ephemeral environments. It covers engineers, coding agents, and external collaborators through configurable isolation, default-deny egress, staged enablement, auditable model policy, and privacy-conscious telemetry.

This repository is a small, runnable policy and telemetry prototype—not a workspace provisioner or network enforcement product. Platform integrations must enforce the configured controls at the identity, host, network, and model gateway layers.

## Get started

Requires Python 3.9 or later; there are no third-party dependencies.

```sh
python3 src/workspace_blueprint.py validate
python3 src/workspace_blueprint.py authorize \
  --stage governed-cloud --group pilot --model general-assistant \
  --classification internal
python3 src/workspace_blueprint.py normalize-event < sample/agent-event.json
```

The sample authorization command returns a JSON allow/deny decision. The normalization command accepts one JSON event on standard input and emits a normalized JSON event without prompt or code content.

## Blueprint

- [Reference architecture and controls](docs/architecture.md)
- [Setup, configuration, and demonstration scenario](docs/setup.md)
- [Sample policy](config/workspace-policy.json)

Run the focused tests with:

```sh
python3 -m unittest discover -s tests -v
```
