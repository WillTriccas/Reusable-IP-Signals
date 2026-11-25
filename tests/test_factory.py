import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "requirement.json"


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "delivery"

    def command(self, *args, succeeds=True):
        result = subprocess.run(
            [sys.executable, "-m", "factory", *map(str, args), "--output", str(self.output)],
            cwd=ROOT, capture_output=True, text=True, timeout=40,
        )
        self.assertEqual(result.returncode == 0, succeeds, result.stdout + result.stderr)
        return result

    def test_delivery_gates_and_trace(self):
        self.command("plan", SAMPLE)
        backlog = json.loads((self.output / "backlog.json").read_text())
        self.assertEqual([epic["id"] for epic in backlog["epics"]], ["E1", "E2"])
        self.assertEqual(backlog["epics"][1]["stories"][0]["acceptance_criteria"][0]["id"], "AC2.1.1")
        self.command("implement", succeeds=False)
        self.command("approve", "plan", "--reviewer", "Demo reviewer")
        self.command("implement")
        self.command("prepare", succeeds=False)
        self.command("verify")
        review = json.loads((self.output / "review.json").read_text())
        self.assertEqual(review["result"], "passed")
        self.assertEqual(review["trace"][0]["story"], "S1.1")
        self.command("prepare", succeeds=False)
        self.command("approve", "implementation", "--reviewer", "Demo reviewer")
        self.command("prepare")
        self.assertIn("runAsNonRoot: true", (self.output / "deploy/deployment.yaml").read_text())
        self.command("approve", "deployment", "--reviewer", "Demo reviewer")
        state = json.loads((self.output / "state.json").read_text())
        self.assertEqual(state["approvals"], ["plan", "implementation", "deployment"])
        self.assertEqual(state["audit"][-1]["reviewer"], "Demo reviewer")
        self.assertEqual(state["stage"], "prepared")

    def test_rejects_tampering_and_repeat_approval(self):
        self.command("plan", SAMPLE)
        self.command("approve", "plan", "--reviewer", "Reviewer")
        self.command("approve", "plan", "--reviewer", "Reviewer", succeeds=False)
        (self.output / "backlog.json").write_text("{}")
        self.assertIn("artifact changed", self.command("implement", succeeds=False).stderr)

    def test_rejects_claimed_stage_without_artifacts(self):
        self.command("plan", SAMPLE)
        state_path = self.output / "state.json"
        state = json.loads(state_path.read_text())
        state["stage"] = "prepared"
        state["approvals"] = ["plan", "implementation", "deployment"]
        state_path.write_text(json.dumps(state))
        self.assertIn("artifacts do not match stage", self.command("status", succeeds=False).stderr)

    def test_rejects_untrusted_slug_and_existing_output(self):
        source = Path(self.temp.name) / "invalid.json"
        data = json.loads(SAMPLE.read_text())
        data["slug"] = "../../unsafe"
        source.write_text(json.dumps(data))
        self.command("plan", source, succeeds=False)
        self.assertFalse(self.output.exists())
        self.command("plan", SAMPLE)
        self.command("plan", SAMPLE, succeeds=False)


if __name__ == "__main__":
    unittest.main()
