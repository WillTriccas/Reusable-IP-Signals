import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from legacy_accelerator.analysis import analyze, render_report


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "legacy_app"


class AnalysisTests(unittest.TestCase):
    def test_synthetic_sample_has_traceable_outputs(self):
        result = analyze(SAMPLE)
        self.assertIn("orders.record_order", {b["function"] for b in result["behaviors"]})
        self.assertIn(
            ("orders.record_order", "pricing.calculate_total"),
            {(d["from"], d["to"]) for d in result["dependencies"]},
        )
        self.assertIn(
            ("orders", "replatform"), {(t["module"], t["path"]) for t in result["treatments"]}
        )
        self.assertIn(
            ("pricing", "retain"), {(t["module"], t["path"]) for t in result["treatments"]}
        )
        self.assertNotIn("__init__", {t["module"] for t in result["treatments"]})
        self.assertIn(
            "arithmetic calculation",
            next(b for b in result["behaviors"] if b["function"] == "pricing.calculate_total")[
                "observed_operations"
            ],
        )
        self.assertTrue(any("SQLite" in r["risk"] for r in result["risks"]))
        self.assertEqual(len(result["phases"]), 4)
        self.assertTrue(result["backlog"])
        for item in result["behaviors"] + result["dependencies"] + result["risks"]:
            self.assertRegex(item["evidence"], r"^[^/]+(?:/[^/]+)*\.py:\d+$")
        self.assertIn("## Dependency map", render_report(result))
        self.assertIn("## Modernization backlog", render_report(result))

    def test_dynamic_sql_and_execution_are_evidence_backed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.py"
            path.write_text(
                "def lookup(db, value):\n"
                "    db.execute('SELECT * FROM items WHERE id = ' + value)\n"
                "    return eval(value)\n",
                encoding="utf-8",
            )
            result = analyze(path)
        self.assertEqual(result["treatments"][0]["path"], "rewrite")
        self.assertEqual(
            {risk["evidence"] for risk in result["risks"]}, {"legacy.py:2", "legacy.py:3"}
        )
        self.assertEqual(result["backlog"][0]["priority"], "P1")

    def test_empty_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "no Python files"):
                analyze(directory)
            path = Path(directory) / "invalid.py"
            path.write_text("def oops(:\n", encoding="utf-8")
            with self.assertRaises(SyntaxError):
                analyze(path)

    def test_external_import_is_rehost_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "adapter.py").write_text(
                "import vendor_sdk\n\ndef load():\n    return vendor_sdk.fetch()\n",
                encoding="utf-8",
            )
            result = analyze(directory)
        self.assertEqual(result["treatments"][0]["path"], "rehost")
        self.assertEqual(result["treatments"][0]["evidence"], ["adapter.py:1"])

    def test_cli_writes_both_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out"
            subprocess.run(
                [sys.executable, "-m", "legacy_accelerator", str(SAMPLE),
                 "--output", str(output)],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            result = json.loads((output / "assessment.json").read_text(encoding="utf-8"))
            self.assertEqual(result["proof_of_value"]["files_scanned"], 5)
            self.assertIn("Proof of value", (output / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
