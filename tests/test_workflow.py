import json
import unittest
from pathlib import Path

from finance_harness import ReviewDecision, WorkflowOrchestrator
from finance_harness.agents import PurchaseOrderMatchAgent


ROOT = Path(__file__).resolve().parents[1]


def sample_payload():
    return json.loads((ROOT / "data" / "sample_invoice.json").read_text(encoding="utf-8"))


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = WorkflowOrchestrator()
        self.payload = sample_payload()

    def test_approval_requires_and_records_human_review(self):
        result = self.workflow.run(
            self.payload,
            reviewer=lambda invoice: ReviewDecision("reviewer-1", True, "Synthetic review passed."),
        )

        self.assertEqual(result.status, "approved")
        self.assertEqual(
            [event.event for event in result.audit_events][-2:],
            ["human_review_completed", "workflow_completed"],
        )
        self.assertEqual(result.audit_events[-2].details["reviewer_id"], "reviewer-1")

    def test_passing_invoice_without_reviewer_stops_at_review_gate(self):
        result = self.workflow.run(self.payload)

        self.assertEqual(result.status, "needs_review")
        self.assertEqual(result.audit_events[-1].event, "human_review_requested")
        self.assertNotIn("human_review_completed", [event.event for event in result.audit_events])

    def test_purchase_order_mismatch_is_held_without_review(self):
        self.payload["purchase_order"]["amount"] = "1200.00"
        reviewer_called = False

        def reviewer(_invoice):
            nonlocal reviewer_called
            reviewer_called = True
            return ReviewDecision("reviewer-1", True, "Should not be called.")

        result = self.workflow.run(self.payload, reviewer=reviewer)

        self.assertEqual(result.status, "held")
        self.assertIn("Invoice amount does not match purchase order", result.findings)
        self.assertFalse(reviewer_called)

    def test_rejection_is_recorded_as_a_distinct_outcome(self):
        result = self.workflow.run(
            self.payload,
            reviewer=lambda invoice: ReviewDecision("reviewer-2", False, "Needs correction."),
        )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.audit_events[-1].details["status"], "rejected")

    def test_agent_exception_fails_closed_and_audits_type_only(self):
        class BrokenMatcher(PurchaseOrderMatchAgent):
            def match(self, invoice, purchase_order):
                raise RuntimeError("sensitive source text")

        result = WorkflowOrchestrator(matcher=BrokenMatcher()).run(self.payload)

        self.assertEqual(result.status, "exception")
        self.assertEqual(result.findings, ("Workflow stopped safely (RuntimeError)",))
        self.assertEqual(result.audit_events[-1].event, "workflow_exception")
        self.assertEqual(result.audit_events[-1].details, {"error_type": "RuntimeError"})

    def test_invalid_reviewer_record_fails_closed(self):
        result = self.workflow.run(
            self.payload,
            reviewer=lambda invoice: ReviewDecision("", True, ""),
        )

        self.assertEqual(result.status, "exception")
        self.assertEqual(result.audit_events[-1].event, "workflow_exception")

    def test_invalid_invoice_data_is_held(self):
        self.payload["invoice"]["amount"] = "-1"

        result = self.workflow.run(self.payload)

        self.assertEqual(result.status, "held")
        self.assertIn("Invoice amount must be a positive finite number", result.findings)


if __name__ == "__main__":
    unittest.main()
