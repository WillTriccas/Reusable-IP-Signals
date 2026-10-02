from collections.abc import Callable
from typing import Any

from .agents import InvoiceValidationAgent, PurchaseOrderMatchAgent
from .audit import AuditTrail
from .models import (
    Invoice,
    PurchaseOrder,
    ReviewDecision,
    WorkflowResult,
)

Reviewer = Callable[[Invoice], ReviewDecision]


class WorkflowOrchestrator:
    """Coordinates replaceable workflow components and enforces the review gate."""

    def __init__(
        self,
        validator: InvoiceValidationAgent | None = None,
        matcher: PurchaseOrderMatchAgent | None = None,
    ) -> None:
        self.validator = validator or InvoiceValidationAgent()
        self.matcher = matcher or PurchaseOrderMatchAgent()

    def run(
        self,
        payload: dict[str, Any],
        reviewer: Reviewer | None = None,
    ) -> WorkflowResult:
        audit = AuditTrail()
        invoice_id = ""
        findings: tuple[str, ...] = ()
        audit.record("workflow_started")
        try:
            invoice_data = payload["invoice"]
            purchase_order_data = payload["purchase_order"]
            if not isinstance(invoice_data, dict) or not isinstance(purchase_order_data, dict):
                raise ValueError("Invoice and purchase_order must be JSON objects")

            invoice = Invoice.from_dict(invoice_data)
            purchase_order = PurchaseOrder.from_dict(purchase_order_data)
            invoice_id = invoice.invoice_id

            validation_findings = self.validator.validate(invoice)
            audit.record(
                "invoice_validated",
                passed=not validation_findings,
                finding_count=len(validation_findings),
            )
            if validation_findings:
                findings = validation_findings
                audit.record("workflow_held", reason="validation_failed")
                return self._result("held", invoice_id, findings, audit)

            match = self.matcher.match(invoice, purchase_order)
            audit.record(
                "purchase_order_matched",
                matched=match.matched,
                finding_count=len(match.findings),
            )
            if not match.matched:
                findings = match.findings
                audit.record("workflow_held", reason="matching_failed")
                return self._result("held", invoice_id, findings, audit)

            audit.record("human_review_requested")
            if reviewer is None:
                return self._result("needs_review", invoice_id, (), audit)

            decision = reviewer(invoice)
            if not decision.reviewer_id.strip() or not decision.rationale.strip():
                raise ValueError("A reviewer ID and rationale are required")
            if not isinstance(decision.approved, bool):
                raise ValueError("Reviewer decision must be approved or rejected")

            status = "approved" if decision.approved else "rejected"
            audit.record(
                "human_review_completed",
                reviewer_id=decision.reviewer_id,
                decision=status,
                rationale=decision.rationale,
            )
            audit.record("workflow_completed", status=status)
            return self._result(status, invoice_id, (), audit)
        except Exception as error:
            audit.record("workflow_exception", error_type=type(error).__name__)
            return self._result(
                "exception",
                invoice_id,
                (f"Workflow stopped safely ({type(error).__name__})",),
                audit,
            )

    @staticmethod
    def _result(
        status: str,
        invoice_id: str,
        findings: tuple[str, ...],
        audit: AuditTrail,
    ) -> WorkflowResult:
        return WorkflowResult(status, invoice_id, findings, audit.events)
