"""Read-only sample service. Replace with reviewed implementation for real requirements."""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SERVICE = "__SERVICE_SLUG__"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            payload = {"status": "ok"}
        elif self.path == "/":
            payload = {"service": SERVICE}
        else:
            self.send_error(404)
            return
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer((os.environ.get("HOST", "127.0.0.1"), 8000), Handler).serve_forever()
