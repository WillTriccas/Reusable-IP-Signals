from decimal import Decimal, InvalidOperation

from .models import Invoice, MatchResult, PurchaseOrder


class InvoiceValidationAgent:
    """Checks basic invoice data quality without making business decisions."""

    def validate(self, invoice: Invoice) -> tuple[str, ...]:
        findings = []
        for field in ("invoice_id", "supplier_id", "purchase_order_id"):
            if not getattr(invoice, field).strip():
                findings.append(f"Missing required field: {field}")

        try:
            amount = Decimal(invoice.amount)
            if not amount.is_finite() or amount <= 0:
                findings.append("Invoice amount must be a positive finite number")
        except (InvalidOperation, ValueError):
            findings.append("Invoice amount must be a valid decimal number")

        if len(invoice.currency) != 3 or not invoice.currency.isalpha() or not invoice.currency.isupper():
            findings.append("Currency must be a three-letter uppercase code")
        return tuple(findings)


class PurchaseOrderMatchAgent:
    """Compares invoice details with one supplied purchase order."""

    def match(self, invoice: Invoice, purchase_order: PurchaseOrder) -> MatchResult:
        findings = []
        if invoice.purchase_order_id != purchase_order.purchase_order_id:
            findings.append("Purchase order ID does not match")
        if invoice.supplier_id != purchase_order.supplier_id:
            findings.append("Supplier does not match")
        try:
            if Decimal(invoice.amount) != Decimal(purchase_order.amount):
                findings.append("Invoice amount does not match purchase order")
        except (InvalidOperation, ValueError):
            findings.append("Invoice and purchase order amounts could not be compared")
        if invoice.currency != purchase_order.currency:
            findings.append("Currency does not match purchase order")
        return MatchResult(matched=not findings, findings=tuple(findings))
