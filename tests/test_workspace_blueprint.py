import copy
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from workspace_blueprint import (  # noqa: E402
    authorize_model,
    load_config,
    normalize_event,
    validate_config,
)


class WorkspaceBlueprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(ROOT / "config" / "workspace-policy.json")

    def test_sample_policy_is_valid_and_default_deny(self):
        self.assertIs(validate_config(self.config), self.config)
        self.assertEqual(self.config["model_policy"]["default"], "deny")
        self.assertEqual(
            {profile["network"]["default"] for profile in self.config["workspaces"].values()},
            {"deny"},
        )

    def test_model_policy_allows_only_matching_stage_group_and_classification(self):
        allowed = authorize_model(
            self.config, "governed-cloud", "pilot", "general-assistant", "internal"
        )
        self.assertEqual(
            allowed,
            {"allowed": True, "policy_revision": "sample-v1", "reason": "approved"},
        )

        for request, reason in (
            (("local-only", "pilot", "general-assistant", "internal"), "stage_not_approved"),
            (("governed-cloud", "developer", "general-assistant", "internal"), "group_not_approved"),
            (("governed-cloud", "pilot", "general-assistant", "restricted"), "classification_not_approved"),
            (("governed-cloud", "pilot", "unlisted-model", "public"), "model_not_approved"),
            (("ephemeral", "developer", "general-assistant", "internal"), "group_not_enabled_for_stage"),
        ):
            with self.subTest(reason=reason):
                result = authorize_model(self.config, *request)
                self.assertEqual(
                    result,
                    {
                        "allowed": False,
                        "policy_revision": "sample-v1",
                        "reason": reason,
                    },
                )

    def test_policy_rejects_non_default_deny_egress(self):
        policy = copy.deepcopy(self.config)
        policy["workspaces"]["cloud"]["network"]["default"] = "allow"
        with self.assertRaisesRegex(ValueError, "default to deny"):
            validate_config(policy)

    def test_event_normalization_drops_prompt_and_unknown_attributes(self):
        event = json.loads((ROOT / "sample" / "agent-event.json").read_text(encoding="utf-8"))
        normalized = normalize_event(event, self.config["telemetry"]["schema_version"])

        self.assertEqual(normalized["schema_version"], "1.0")
        self.assertEqual(normalized["attributes"], {
            "model_id": "general-assistant",
            "policy_reason": "approved",
        })
        self.assertNotIn("prompt", json.dumps(normalized))
        self.assertNotIn("prompt", normalized)

    def test_event_normalization_rejects_invalid_duration(self):
        event = {
            "timestamp": "2026-01-15T10:30:00Z",
            "workspace_id": "demo",
            "workspace_type": "local",
            "actor_type": "engineer",
            "event_type": "workspace_start",
            "outcome": "success",
            "duration_ms": -1,
        }
        with self.assertRaisesRegex(ValueError, "duration_ms"):
            normalize_event(event)

    def test_event_normalization_requires_timezone_qualified_timestamp(self):
        event = {
            "timestamp": "2026-01-15T10:30:00",
            "workspace_id": "demo",
            "workspace_type": "local",
            "actor_type": "engineer",
            "event_type": "workspace_start",
            "outcome": "success",
        }
        with self.assertRaisesRegex(ValueError, "timezone"):
            normalize_event(event)


if __name__ == "__main__":
    unittest.main()
