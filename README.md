# Reusable-IP-Signals
 I have a process that collects explicit or strongly evidenced requests discussed in my completed Teams meetings for a new demo, showcase, prototype, accelerator, technical capability, or reusable functionality. Notify Will privately through this automation's Teams result only when a credible new signal or new occurrence is found. 

## Governed multi-model gateway accelerator

This customer-neutral, standard-library Python prototype demonstrates a control
layer for synthetic AI and coding-assistant requests. It uses two interchangeable
mock providers; it does not connect to real services or require credentials.
Python 3.10 or later is required.

From the repository root:

```sh
python3 -m governed_gateway examples/gateway_scenario.json
python3 -m unittest discover -s tests -v
```

The scenario prints JSON containing per-request results, audit/telemetry events,
and per-principal spend. It deliberately fails `mock_a`, routes the first request
to approved `model_b`, redacts a synthetic email, denies an unapproved model,
and then denies a revoked principal. Change the scenario's provider failure
flags, routes, rates, limits, principals, approvals, or requests to explore
other behaviors. Scenario inputs and provider responses must be synthetic.

### Architecture and control flow

```
synthetic request -> principal/revocation -> rate window -> role/task policy
                  -> sensitive-data filter -> input limit
                  -> approved route + budget check -> mock provider(s)
                  -> result + audit decisions / attempt telemetry
```

* The configuration maps each task to an ordered list of model names and
  specifies allowed roles. Unknown tasks, missing roles, unknown principals,
  and revoked principals are denied. Identities are simulated identifiers, not
  authenticated users.
* Models must first be proposed with a known provider and non-negative rates,
  then explicitly approved with an approver identifier. A duplicate proposal
  is rejected, so an approval cannot silently apply to a replacement model.
  An unapproved or unknown model is skipped, including during failover.
* The filter either redacts or denies simple email and `password`, `token`, or
  `api_key` assignment patterns before a provider is called. It is an
  illustrative pattern matcher, **not** comprehensive DLP; it cannot detect
  all secrets or sensitive data.
* The rolling per-principal rate window counts requests that pass access
  checks, including policy denials, and records `rate_limited` decisions as an
  abuse signal. Unknown or revoked identities are denied before the window.
* A failed mock attempt falls back to the next approved, affordable model in
  the same task route. Each mock failure happens before usage and costs zero;
  no automatic retry of the same model occurs.
* Usage is measured in whitespace-separated **synthetic units**, not real
  model tokens. Each model has integer microcredit rates per input and output
  unit. Before each call, the gateway checks current principal spend plus
  input cost and the maximum output cost against the principal's budget.
  Successful calls debit actual mock usage. Budgets have no time reset and
  last only for the lifetime of the gateway instance.

### Telemetry and audit

The `telemetry` array contains model proposal/approval and access revocation
events, a `decision` for every request, and one `provider_attempt` per call.
Decisions include a generated request ID, principal, task, outcome and total
latency in milliseconds; successful decisions also include the chosen model,
cost and sensitive match count. Attempt events link to the same request ID and
include model, provider, success/failure, latency, input/output units and cost
in microcredits. Aggregate attempts by principal, model or provider for usage
and cost; count failure, decision outcomes and `rate_limited` events for
reliability, policy and abuse monitoring. Latencies use a monotonic clock.
Telemetry intentionally omits prompts, responses and provider exception text.
Identifiers themselves should never contain sensitive information.

### Safety and production boundary

This is a single-process educational prototype, **not a security boundary or a
deployable proxy**. Its principals, approvals and provider health are locally
supplied data; approval and revocation operations have no authentication,
authorization, separation of duties or durable audit trail. State, budgets,
rate windows and telemetry are in memory, reset on restart and are not safe
for concurrent or distributed use. The mock provider keeps received prompts
in memory for testing. There is no network server, real model adapter, model
output filtering, timeout, token accounting or billing reconciliation.

Before adapting this pattern for real traffic, add authenticated and authorized
control-plane and request identities, durable tamper-resistant audit and
centralized atomic quota enforcement, vetted DLP and data classification,
provider-specific token/cost reconciliation (including failures that may incur
charges), secure provider integrations, timeouts and bounded retries, and
privacy-aware retention and monitoring. Do not send real or sensitive data to
this demonstration.
