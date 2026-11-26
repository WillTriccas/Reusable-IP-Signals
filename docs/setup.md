# Setup and demonstration

## Prerequisites

- Python 3.9 or later
- No external packages, credentials, or cloud account are required for the local demonstration

## Validate and try the policy

From the repository root:

```sh
python3 src/workspace_blueprint.py validate
python3 src/workspace_blueprint.py authorize \
  --stage governed-cloud --group pilot --model general-assistant \
  --classification internal
```

The second command prints an allowed decision. Try `--stage local-only` or `--classification restricted` to see the default-deny policy deny the request. The command evaluates the sample policy only; it is not a substitute for an enforced model gateway.

## Normalize an agent event

```sh
python3 src/workspace_blueprint.py normalize-event < sample/agent-event.json
```

The emitted event includes workspace, actor, event, outcome, and selected operational attributes. Input fields outside the telemetry contract are discarded, including any prompt or code content. Do not put real personal, customer, or secret data in demonstration events.

## Configuration and integration

Edit `config/workspace-policy.json` through the normal code-review process to change stages, group-to-stage eligibility, workspace isolation or egress declarations, model eligibility, and telemetry options. Keep the default-deny egress and model policy explicit. `validate` checks the expected structure and security defaults. Model decisions include the policy version so gateway adapters can associate an audit event with the reviewed configuration.

For a real deployment, connect the policy to adapters that:

1. Provision the appropriate local, managed cloud, or ephemeral workspace and enforce the declared isolation and egress at runtime.
2. Bind user and agent identity to approved groups and enablement stages.
3. Evaluate model requests at a gateway before forwarding them, including data classification, quotas, budgets, and revocation.
4. Send normalized telemetry to the approved monitoring and audit systems with suitable access and retention controls.

The reference does not prescribe a cloud, identity provider, model vendor, telemetry backend, or infrastructure tool.
