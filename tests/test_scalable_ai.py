import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "scalable-ai"
sys.path.insert(0, str(EXAMPLE_DIR))

import app


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((EXAMPLE_DIR / "platform.json").read_text(encoding="utf-8"))

    def test_reference_configuration_has_two_independent_workloads(self):
        app.validate_config(self.config)
        self.assertEqual({item["name"] for item in self.config["workloads"]}, {"triage", "summary"})
        self.assertEqual(len({item["port"] for item in self.config["workloads"]}), 2)

    def test_rejects_shared_workload_ports(self):
        self.config["workloads"][1]["port"] = self.config["workloads"][0]["port"]
        with self.assertRaisesRegex(ValueError, "duplicate port"):
            app.validate_config(self.config)

    def test_rejects_overlapping_routes(self):
        self.config["workloads"][1]["route"] = "/triage/summary"
        with self.assertRaisesRegex(ValueError, "overlapping route"):
            app.validate_config(self.config)


class LocalDeploymentTests(unittest.TestCase):
    def test_gateway_routes_two_workloads_and_requires_authentication(self):
        config = json.loads((EXAMPLE_DIR / "platform.json").read_text(encoding="utf-8"))
        config["gateway"]["port"] = unused_port()
        for workload in config["workloads"]:
            workload["port"] = unused_port()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8") as file:
            json.dump(config, file)
            file.flush()
            env = {**os.environ, "DEMO_API_TOKEN": "test-only-token"}
            process = subprocess.Popen(
                [sys.executable, str(EXAMPLE_DIR / "app.py"), "run", "--config", file.name],
                cwd=EXAMPLE_DIR,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            base_url = f"http://127.0.0.1:{config['gateway']['port']}"
            try:
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        with urllib.request.urlopen(base_url + "/healthz", timeout=0.5):
                            break
                    except (urllib.error.URLError, TimeoutError):
                        time.sleep(0.1)
                else:
                    self.fail("local reference gateway did not start")

                self.assert_inference(
                    base_url + "/triage/infer",
                    "An outage is blocking the release",
                    {"workload": "triage", "label": "urgent", "confidence": 0.91, "synthetic": True},
                )
                self.assert_inference(
                    base_url + "/summary/infer",
                    "Synthetic first sentence. Synthetic second sentence.",
                    {"workload": "summary", "summary": "Synthetic first sentence", "synthetic": True},
                )
                request = urllib.request.Request(
                    base_url + "/triage/infer",
                    data=b'{"text":"hello"}',
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request, timeout=2)
                self.assertEqual(error.exception.code, 401)
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                    process.wait(timeout=5)

    def assert_inference(self, url, text, expected):
        request = urllib.request.Request(
            url,
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + "test-only-token",
                "Content-Type": "application/json",
                "X-Request-Id": "test-request",
            },
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            self.assertEqual(response.headers["X-Request-Id"], "test-request")
            self.assertEqual(json.load(response), expected)


if __name__ == "__main__":
    unittest.main()
