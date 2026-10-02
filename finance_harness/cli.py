import argparse
import json
from pathlib import Path

from .models import Invoice, ReviewDecision
from .workflow import WorkflowOrchestrator


def _reviewer(args: argparse.Namespace):
    def review(invoice: Invoice) -> ReviewDecision:
        print(f"\nHuman review required for {invoice.invoice_id}.")
        reviewer_id = args.reviewer_id or input("Reviewer ID: ").strip()
        choice = args.review_decision or input("Decision [approve/reject]: ").strip().lower()
        while choice not in ("approve", "reject"):
            choice = input("Enter approve or reject: ").strip().lower()
        rationale = (
            "Synthetic demonstration reviewer decision."
            if args.review_decision
            else input("Rationale: ").strip()
        )
        return ReviewDecision(reviewer_id, choice == "approve", rationale)

    return review


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the synthetic invoice review showcase.")
    parser.add_argument("--input", type=Path, required=True, help="Path to a synthetic workflow JSON file")
    parser.add_argument("--review-decision", choices=("approve", "reject"))
    parser.add_argument("--reviewer-id", help="Reviewer identity for a non-interactive demo decision")
    args = parser.parse_args()

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        result = WorkflowOrchestrator().run(payload, reviewer=_reviewer(args))
    except (OSError, json.JSONDecodeError) as error:
        parser.error(f"could not read workflow input: {error}")

    print(f"\nWorkflow status: {result.status}")
    if result.findings:
        print("Findings:")
        for finding in result.findings:
            print(f"- {finding}")
    print("Audit trail:")
    for event in result.audit_events:
        print(f"{event.sequence}. {event.event}: {event.details}")
    return 0 if result.status in ("approved", "rejected", "held", "needs_review") else 1
