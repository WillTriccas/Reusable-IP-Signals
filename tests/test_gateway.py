import json
import unittest

from governed_gateway import Gateway, MockProvider, Model, Policy, Principal, Request


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.a = MockProvider()
        self.b = MockProvider()
        self.now = 0
        self.gateway = Gateway(
            Policy(routes={"code": ("a", "b"), "chat": ("b",)}, allowed_roles=frozenset({"developer"}),
                   max_output_units=5, rate_limit=3, rate_window_seconds=10),
            [Principal("dev", frozenset({"developer"}), 100)],
            {"one": self.a, "two": self.b}, clock=lambda: self.now,
        )
        self.gateway.propose_model(Model("a", "one", 1, 1))
        self.gateway.propose_model(Model("b", "two", 1, 1))

    def request(self, prompt="hello", task="code", principal="dev"):
        return self.gateway.handle(Request(principal, task, prompt))

    def approve(self):
        self.gateway.approve_model("a", "reviewer")
        self.gateway.approve_model("b", "reviewer")

    def test_approval_and_policy_routing(self):
        self.assertEqual(self.request()["outcome"], "no_approved_model")
        self.gateway.approve_model("b", "reviewer")
        self.assertEqual(self.request(task="chat")["outcome"], "allowed")
        self.assertEqual(self.b.received, ["hello"])
        self.assertEqual(self.request(task="unknown")["outcome"], "policy_denied")
        self.assertFalse(self.a.received)

    def test_routes_to_either_provider(self):
        self.approve()
        self.assertEqual(self.request(task="code")["outcome"], "allowed")
        self.assertEqual(self.request(task="chat")["outcome"], "allowed")
        self.assertEqual(self.a.received, ["hello"])
        self.assertEqual(self.b.received, ["hello"])
        attempts = [event for event in self.gateway.telemetry if event["event"] == "provider_attempt"]
        self.assertEqual([event["model"] for event in attempts], ["a", "b"])
        self.assertEqual(self.gateway.spend["dev"], 12)

    def test_failover_filters_and_attributes_usage(self):
        self.approve()
        self.a.fail = True
        result = self.request("Contact sample@example.com " + "password" + "=" + "synthetic-value")
        self.assertEqual(result["outcome"], "allowed")
        self.assertEqual(self.a.received, ["Contact [REDACTED_EMAIL] [REDACTED_SECRET]"])
        self.assertEqual(self.b.received, self.a.received)
        attempts = [event for event in self.gateway.telemetry if event["event"] == "provider_attempt"]
        self.assertEqual([event["outcome"] for event in attempts], ["failure", "success"])
        self.assertEqual(attempts[1]["input_units"], 3)
        self.assertEqual(attempts[1]["output_units"], 5)
        self.assertEqual(attempts[1]["cost_microcredits"], 8)
        self.assertEqual(self.gateway.spend["dev"], 8)
        serialized = json.dumps(self.gateway.telemetry)
        self.assertNotIn("sample@example.com", serialized)
        self.assertNotIn("synthetic-value", serialized)
        self.assertTrue(all(event["latency_ms"] >= 0 for event in attempts))

    def test_denials_and_revocation_never_call_provider(self):
        self.approve()
        self.assertEqual(self.request(principal="unknown")["outcome"], "access_denied")
        self.gateway.revoke_access("dev")
        self.assertEqual(self.request()["outcome"], "access_denied")
        self.assertFalse(self.a.received or self.b.received)
        self.assertEqual(self.gateway.telemetry[-2]["event"], "access_revoked")

    def test_abuse_window_counts_denied_requests(self):
        for _ in range(3):
            self.assertEqual(self.request(task="unknown")["outcome"], "policy_denied")
        self.assertEqual(self.request()["outcome"], "rate_limited")
        self.now = 10
        self.assertEqual(self.request()["outcome"], "no_approved_model")

    def test_budget_is_checked_before_each_failover(self):
        self.gateway.principals["dev"] = Principal("dev", frozenset({"developer"}), 5)
        self.approve()
        self.assertEqual(self.request()["outcome"], "budget_denied")
        self.assertFalse(self.a.received or self.b.received)
        self.gateway.principals["dev"] = Principal("dev", frozenset({"developer"}), 6)
        self.a.fail = True
        self.assertEqual(self.request()["outcome"], "allowed")
        self.assertEqual(self.gateway.spend["dev"], 6)
        self.assertEqual(self.request()["outcome"], "budget_denied")

    def test_failure_does_not_fall_back_to_unapproved_model(self):
        self.gateway.approve_model("a", "reviewer")
        self.a.fail = True
        self.assertEqual(self.request()["outcome"], "providers_failed")
        self.assertFalse(self.b.received)

    def test_deny_sensitive_and_input_limits(self):
        self.gateway.policy = Policy({"code": ("a",)}, frozenset({"developer"}), sensitive_action="deny", max_input_units=1)
        self.approve()
        self.assertEqual(self.request("email sample@example.com")["outcome"], "sensitive_denied")
        self.assertEqual(self.request("two words")["outcome"], "input_limit")
        self.assertFalse(self.a.received)

    def test_quoted_secret_is_redacted_or_denied(self):
        self.approve()
        prompt = '{"' + "password" + '": "fictional value"}'
        self.assertEqual(self.request(prompt)["outcome"], "allowed")
        self.assertEqual(self.a.received, ["{[REDACTED_SECRET]}"])
        self.gateway.policy = Policy({"code": ("a",)}, frozenset({"developer"}), sensitive_action="deny")
        self.assertEqual(self.request(prompt)["outcome"], "sensitive_denied")
        self.assertEqual(len(self.a.received), 1)
        self.assertNotIn("fictional value", json.dumps(self.gateway.telemetry))

    def test_invalid_request_and_role_denied(self):
        self.approve()
        self.gateway.principals["dev"] = Principal("dev", frozenset({"viewer"}), 100)
        self.assertEqual(self.request()["outcome"], "policy_denied")
        self.assertEqual(self.request(principal="bad name")["outcome"], "invalid_request")
        self.assertEqual(self.request(prompt=None)["outcome"], "invalid_request")
        self.assertFalse(self.a.received or self.b.received)

    def test_model_onboarding_rejects_replacement(self):
        self.gateway.approve_model("a", "reviewer")
        with self.assertRaises(ValueError):
            self.gateway.propose_model(Model("a", "two", 0, 0))
        with self.assertRaises(ValueError):
            self.gateway.approve_model("missing", "reviewer")
        with self.assertRaises(ValueError):
            self.gateway.propose_model(Model("c", "missing", 0, 0))


if __name__ == "__main__":
    unittest.main()
