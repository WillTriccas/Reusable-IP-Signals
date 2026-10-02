from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    supplier_id: str
    amount: str
    currency: str
    purchase_order_id: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Invoice":
        return cls(**{field: data.get(field, "") for field in cls.__annotations__})


@dataclass(frozen=True)
class PurchaseOrder:
    purchase_order_id: str
    supplier_id: str
    amount: str
    currency: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PurchaseOrder":
        return cls(**{field: data.get(field, "") for field in cls.__annotations__})


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    findings: tuple[str, ...]


@dataclass(frozen=True)
class ReviewDecision:
    reviewer_id: str
    approved: bool
    rationale: str


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    event: str
    details: dict[str, Any]


@dataclass(frozen=True)
class WorkflowResult:
    status: str
    invoice_id: str
    findings: tuple[str, ...]
    audit_events: tuple[AuditEvent, ...]
