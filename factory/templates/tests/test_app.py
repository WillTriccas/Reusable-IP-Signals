import importlib.util
import json
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from http.server import ThreadingHTTPServer


spec = importlib.util.spec_from_file_location("app", Path(__file__).resolve().parents[1] / "app.py")
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def test_health(self):
        with urlopen(self.url + "/health", timeout=3) as response:
            self.assertEqual(json.load(response), {"status": "ok"})

    def test_service(self):
        with urlopen(self.url + "/", timeout=3) as response:
            self.assertEqual(json.load(response), {"service": "__SERVICE_SLUG__"})

    def test_unknown_route(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + "/missing", timeout=3)
        self.assertEqual(error.exception.code, 404)
