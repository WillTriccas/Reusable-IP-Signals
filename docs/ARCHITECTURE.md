# Architecture and boundaries

## Workflow shape

The harness separates reusable coordination from finance-specific checks:

- `WorkflowOrchestrator` controls the order of stages, routes failures to a held or exception outcome, and never approves an invoice by itself.
- `InvoiceValidationAgent` checks basic required fields and amount/currency shape.
- `PurchaseOrderMatchAgent` compares the invoice to its supplied purchase order.
- A `Reviewer` callback is invoked only after both agents pass. It must return a reviewer identity, a boolean decision, and a rationale. Without a callback, the workflow stops at `needs_review`.
- `AuditTrail` records ordered stage events for every run. It records exception types rather than exception messages to avoid copying arbitrary input into the audit details.

Agent implementations are deterministic, local Python components, not autonomous language models. They can be replaced or extended through the orchestrator's injected validator and matcher components. This keeps orchestration, validation, review policy, and audit behavior independently testable and avoids implying that an AI system has authority to make a payment decision.

## Outcomes and controls

`approved` and `rejected` require a completed human review. Data-quality or matching issues produce `held`; unexpected processing failures produce `exception`; a passing invoice without a reviewer produces `needs_review`. None of these outcomes submits or pays an invoice. Production use would require organization-approved identity, access controls, persistence, retention, and system integrations; those are intentionally outside this showcase.

## Input contract

The CLI accepts a JSON object containing `invoice` and `purchase_order` objects. Each has the corresponding identifiers, supplier, amount as a decimal string, and currency fields shown in `data/sample_invoice.json`. The bundled identifiers and amounts are fabricated solely for demonstration.
