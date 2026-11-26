# Reference architecture

## Workspace topology

```text
 Engineer / coding agent / collaborator
                  |
       Identity, device, and group policy
                  |
    +-------------+-------------------+
    |             |                   |
 Local workspace  Governed cloud      Ephemeral workspace
 user-managed     isolated session    single task, short-lived
    |             |                   |
    +-------- default-deny egress ----+
                  |
       Approved model and tool gateway
          |                       |
   Model policy decision     Normalized telemetry
                                   |
                       Central monitoring / audit
```

Treat local, cloud, and ephemeral environments as distinct trust boundaries. Local workspaces prioritize developer performance but rely on managed-device controls and explicit protection of credentials. Cloud workspaces use centrally managed images, identity-bound sessions, and isolated storage. Ephemeral workspaces are created for a task or collaboration, have bounded access, and are destroyed with their temporary data after completion.

All environments use the same policy vocabulary and telemetry contract. A control plane or infrastructure-as-code adapter should translate this sample configuration into controls provided by the organization’s chosen workspace, identity, network, and model gateway platforms. The prototype does not directly configure or enforce those systems.

## Progressive enablement

The sample policy has three ordered stages:

1. **`local-only`** — local tools and non-sensitive work; model access is not enabled.
2. **`governed-cloud`** — identity-verified cloud workspaces and approved model access for the pilot group and permitted data classifications.
3. **`ephemeral`** — short-lived isolated sessions for approved agents or collaborators, with narrow task permissions and the same model gateway policy.

The `group_stages` mapping configures which groups can enter each stage: `standard` is local-only, `developer` can use governed cloud, and `pilot` can use all three. Promotion between stages should be explicit and auditable, based on training, device or session posture, business approval, and monitoring readiness. Start at the least capable stage needed. Rollback or disablement should be available without rebuilding a workspace.

## Isolation and egress

The example defines a workspace profile for each environment. Profiles declare isolation intent and use `default: deny` for network egress; only listed destinations are eligible for access. Use separate identities and storage boundaries for each workspace, avoid shared credentials, and scope collaborator permissions to the task.

These are policy inputs, not firewall rules. A deployment must implement and verify them in the actual runtime (for example, through network policy, proxy allowlists, managed endpoints, and identity-aware access). Do not interpret an allowlist entry as proof that egress is blocked elsewhere.

## Model usage controls

Route agent and developer model requests through a policy gateway. The sample policy uses an explicit model allowlist, permitted enablement stages, groups, and data classifications; requests not matching an entry are denied. A production gateway should additionally enforce per-user and per-model quotas, cost budgets, retention settings, approved tools, and a rapid revocation/kill switch.

Record policy changes as reviewed, version-controlled configuration. Emit the policy version and decision reason to audit telemetry. Do not send secrets, restricted data, or prompts to a model unless a separately approved policy and gateway explicitly permit that use.

## Normalized telemetry

The CLI emits a stable event with:

| Field | Meaning |
| --- | --- |
| `schema_version` | Normalized contract version |
| `timestamp` | Event time supplied by the source |
| `workspace_id`, `workspace_type` | Workspace identity and local/cloud/ephemeral type |
| `actor_type` | Engineer, agent, or collaborator |
| `event_type`, `outcome` | Operation category and result |
| `duration_ms` | Optional non-negative duration |
| `attributes` | Optional allowlisted operational metadata |

Prompt and code content are deliberately excluded. Only known operational attributes are copied; unknown keys such as prompt text are dropped. Production adapters should also apply identity minimization, retention limits, access controls, and a privacy review before sending events to a monitoring platform.
