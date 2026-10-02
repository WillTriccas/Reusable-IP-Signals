# Finance Process Agentic Harness Showcase

A small, runnable, customer-neutral demonstration of a finance workflow harness. It processes synthetic invoice and purchase-order data, checks the match, records an audit trail, and pauses for a human decision. An approval is only a workflow outcome: this prototype does not initiate payments or connect to financial systems.

## Run the showcase

Requires Python 3.10 or newer; no third-party packages are needed.

```bash
python -m finance_harness --input data/sample_invoice.json
```

When the invoice passes validation and matching, the CLI asks for a reviewer ID, approval or rejection, and rationale. For a repeatable, non-interactive run, supply the synthetic reviewer decision explicitly:

```bash
python -m finance_harness --input data/sample_invoice.json \
  --review-decision approve --reviewer-id demo-reviewer
```

`--review-decision` is a convenience for demonstrations and tests, not a way to bypass the workflow gate: every successful case still records a reviewer identity, decision, and rationale. To run the tests:

```bash
python -m unittest discover -s tests -v
```

## What the workflow demonstrates

1. A validation agent checks required invoice fields and basic amount/currency rules.
2. A matching agent compares the invoice with its purchase order.
3. The orchestrator routes validation or matching problems to a held outcome and records exceptions without treating them as approvals.
4. If checks pass, the workflow requests a human review. Only a recorded human approval produces an `approved` result; rejection is recorded as `rejected`.
5. Each stage appends a structured event to the workflow audit trail.

See [the architecture guide](docs/ARCHITECTURE.md) for component boundaries and extension points.

All included records and reviewer labels are synthetic. Do not use this prototype with real financial records or production systems.
