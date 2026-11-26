"""Policy evaluation and telemetry for a synthetic, single-process gateway."""

from collections import defaultdict, deque
from dataclasses import dataclass, field
import re
import time
import uuid


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SECRET = re.compile(
    r"""(?<!\w)["']?(?:api[_-]?key|password|token)\b["']?\s*[:=]\s*"""
    r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;}\]]+)""",
    re.I,
)


def _identifier(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("identifiers must contain 1-64 letters, digits, '.', '_' or '-'")
    return value


@dataclass(frozen=True)
class Principal:
    name: str
    roles: frozenset[str]
    budget_microcredits: int

    def __post_init__(self):
        _identifier(self.name)
        if self.budget_microcredits < 0:
            raise ValueError("budget must be non-negative")
        for role in self.roles:
            _identifier(role)


@dataclass(frozen=True)
class Model:
    name: str
    provider: str
    input_rate: int
    output_rate: int

    def __post_init__(self):
        _identifier(self.name)
        _identifier(self.provider)
        if self.input_rate < 0 or self.output_rate < 0:
            raise ValueError("rates must be non-negative")


@dataclass(frozen=True)
class Policy:
    routes: dict[str, tuple[str, ...]]
    allowed_roles: frozenset[str]
    sensitive_action: str = "redact"
    max_input_units: int = 100
    max_output_units: int = 20
    rate_limit: int = 10
    rate_window_seconds: float = 60

    def __post_init__(self):
        if self.sensitive_action not in {"redact", "deny"}:
            raise ValueError("sensitive_action must be redact or deny")
        if self.max_input_units < 1 or self.max_output_units < 1 or self.rate_limit < 1 or self.rate_window_seconds <= 0:
            raise ValueError("limits must be positive")
        for task, models in self.routes.items():
            _identifier(task)
            for model in models:
                _identifier(model)
        for role in self.allowed_roles:
            _identifier(role)


@dataclass(frozen=True)
class Request:
    principal: str
    task: str
    prompt: str


@dataclass
class MockProvider:
    """Deterministic provider; failures occur before any usage is incurred."""

    fail: bool = False
    received: list[str] = field(default_factory=list)

    def generate(self, prompt, max_output_units):
        self.received.append(prompt)
        if self.fail:
            raise RuntimeError("simulated provider failure")
        return " ".join("Synthetic response from mock provider".split()[:max_output_units])


class Gateway:
    """Sequential in-memory control plane and data plane for synthetic traffic."""

    def __init__(self, policy, principals, providers, clock=time.monotonic):
        self.policy = policy
        self.principals = {principal.name: principal for principal in principals}
        self.providers = dict(providers)
        self.clock = clock
        self.models = {}
        self.approvals = {}
        self.revoked = set()
        self.spend = defaultdict(int)
        self.attempts = defaultdict(deque)
        self.telemetry = []

    def propose_model(self, model):
        if model.name in self.models:
            raise ValueError("model already proposed")
        if model.provider not in self.providers:
            raise ValueError("unknown provider")
        self.models[model.name] = model
        self.telemetry.append({"event": "model_proposed", "model": model.name})

    def approve_model(self, name, approver):
        _identifier(approver)
        if name not in self.models:
            raise ValueError("unknown model")
        self.approvals[name] = approver
        self.telemetry.append({"event": "model_approved", "model": name, "approver": approver})

    def revoke_access(self, name):
        if name not in self.principals:
            raise ValueError("unknown principal")
        self.revoked.add(name)
        self.telemetry.append({"event": "access_revoked", "principal": name})

    def handle(self, request):
        started = self.clock()
        request_id = uuid.uuid4().hex

        def finish(outcome, **values):
            event = {
                "event": "decision", "request_id": request_id,
                "principal": request.principal if isinstance(request.principal, str) and _IDENTIFIER.fullmatch(request.principal) else "invalid",
                "task": request.task if isinstance(request.task, str) and _IDENTIFIER.fullmatch(request.task) else "invalid",
                "outcome": outcome, "latency_ms": round(max(0, self.clock() - started) * 1000, 3),
            }
            event.update(values)
            self.telemetry.append(event)
            return {"request_id": request_id, "outcome": outcome}

        if not isinstance(request.principal, str) or not _IDENTIFIER.fullmatch(request.principal):
            return finish("invalid_request")
        if not isinstance(request.task, str) or not _IDENTIFIER.fullmatch(request.task) or not isinstance(request.prompt, str):
            return finish("invalid_request")
        principal = self.principals.get(request.principal)
        if principal is None or request.principal in self.revoked:
            return finish("access_denied")

        now = self.clock()
        attempts = self.attempts[principal.name]
        while attempts and now - attempts[0] >= self.policy.rate_window_seconds:
            attempts.popleft()
        if len(attempts) >= self.policy.rate_limit:
            return finish("rate_limited")
        attempts.append(now)

        routes = self.policy.routes.get(request.task, ())
        if not routes or not (principal.roles & self.policy.allowed_roles):
            return finish("policy_denied")
        filtered, emails = _EMAIL.subn("[REDACTED_EMAIL]", request.prompt)
        filtered, secrets = _SECRET.subn("[REDACTED_SECRET]", filtered)
        sensitive = emails + secrets
        if sensitive and self.policy.sensitive_action == "deny":
            return finish("sensitive_denied", sensitive_matches=sensitive)
        input_units = len(filtered.split())
        if input_units > self.policy.max_input_units:
            return finish("input_limit", sensitive_matches=sensitive)

        eligible = False
        affordable = False
        for name in routes:
            model = self.models.get(name)
            if model is None or name not in self.approvals:
                continue
            eligible = True
            estimate = input_units * model.input_rate + self.policy.max_output_units * model.output_rate
            if self.spend[principal.name] + estimate > principal.budget_microcredits:
                continue
            affordable = True
            attempt_started = self.clock()
            try:
                response = self.providers[model.provider].generate(filtered, self.policy.max_output_units)
            except Exception:
                self.telemetry.append({
                    "event": "provider_attempt", "request_id": request_id,
                    "principal": principal.name, "task": request.task, "model": name,
                    "provider": model.provider, "outcome": "failure",
                    "latency_ms": round(max(0, self.clock() - attempt_started) * 1000, 3),
                    "input_units": 0, "output_units": 0, "cost_microcredits": 0,
                })
                continue
            output_units = len(response.split())
            cost = input_units * model.input_rate + output_units * model.output_rate
            self.spend[principal.name] += cost
            self.telemetry.append({
                "event": "provider_attempt", "request_id": request_id,
                "principal": principal.name, "task": request.task, "model": name,
                "provider": model.provider, "outcome": "success",
                "latency_ms": round(max(0, self.clock() - attempt_started) * 1000, 3),
                "input_units": input_units, "output_units": output_units, "cost_microcredits": cost,
            })
            result = finish("allowed", model=name, sensitive_matches=sensitive, cost_microcredits=cost)
            result["response"] = response
            return result
        if not eligible:
            return finish("no_approved_model", sensitive_matches=sensitive)
        if not affordable:
            return finish("budget_denied", sensitive_matches=sensitive)
        return finish("providers_failed", sensitive_matches=sensitive)
