from .models import AuditEvent


class AuditTrail:
    """Collects ordered, structured events for one workflow execution."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(self, event: str, **details: object) -> None:
        self._events.append(AuditEvent(len(self._events) + 1, event, details))

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)
