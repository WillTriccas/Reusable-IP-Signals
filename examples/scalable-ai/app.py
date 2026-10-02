#!/usr/bin/env python3
"""Dependency-free local reference platform for two synthetic AI workloads."""

import argparse
import hmac
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY_BYTES = 1_000_000
LOCAL_HOSTS = {"127.0.0.1", "localhost"}
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
ENV_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def load_config(path):
    with open(path, encoding="utf-8") as config_file:
        config = json.load(config_file)
    validate_config(config)
    return config


def validate_config(config):
    gateway = config.get("gateway", {})
    workloads = config.get("workloads", [])
    if gateway.get("host") not in LOCAL_HOSTS:
        raise ValueError("the reference gateway must bind to localhost")
    if not _valid_port(gateway.get("port")):
        raise ValueError("gateway port must be between 1 and 65535")
    if not ENV_PATTERN.fullmatch(gateway.get("token_env", "")):
        raise ValueError("gateway token_env must be an environment variable name")
    if not isinstance(workloads, list) or not workloads:
        raise ValueError("at least one workload is required")

    names = set()
    routes = set()
    ports = {gateway["port"]}
    for workload in workloads:
        name = workload.get("name", "")
        route = workload.get("route", "")
        if not NAME_PATTERN.fullmatch(name) or name in names:
            raise ValueError(f"invalid or duplicate workload name: {name!r}")
        if workload.get("kind") not in {"triage", "summary"}:
            raise ValueError(f"unsupported workload kind for {name!r}")
        if workload.get("host") not in LOCAL_HOSTS:
            raise ValueError(f"workload {name!r} must bind to localhost")
        if not _valid_port(workload.get("port")) or workload["port"] in ports:
            raise ValueError(f"invalid or duplicate port for workload {name!r}")
        if not route.startswith("/") or route == "/" or route.endswith("/"):
            raise ValueError(f"invalid route for workload {name!r}")
        if any(route == other or route.startswith(other + "/") or
               other.startswith(route + "/") for other in routes):
            raise ValueError(f"duplicate or overlapping route for workload {name!r}")
        names.add(name)
        routes.add(route)
        ports.add(workload["port"])


def _valid_port(port):
    return isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535


def infer(kind, payload):
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("'text' must be a non-empty string")
    if kind == "triage":
        lowered = text.lower()
        label = "urgent" if any(word in lowered for word in ("urgent", "outage", "blocked")) else "review"
        return {"label": label, "confidence": 0.91, "synthetic": True}
    return {"summary": text.strip().split(".")[0].strip(), "synthetic": True}


def _send_json(handler, status, data, request_id=None):
    body = json.dumps(data).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    if request_id:
        handler.send_header("X-Request-Id", request_id)
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler):
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError as error:
        raise ValueError("invalid content length") from error
    if length < 0 or length > MAX_BODY_BYTES:
        raise ValueError("request body exceeds the 1 MB limit")
    try:
        return json.loads(handler.rfile.read(length))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("request body must be valid JSON") from error


class WorkloadHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            _send_json(self, 200, {"status": "ok", "workload": self.server.workload["name"]})
        else:
            _send_json(self, 404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/infer":
            _send_json(self, 404, {"error": "not found"})
            return
        try:
            result = infer(self.server.workload["kind"], _read_json(self))
        except ValueError as error:
            _send_json(self, 400, {"error": str(error)})
            return
        _send_json(self, 200, {"workload": self.server.workload["name"], **result})

    def log_message(self, *_):
        pass


class GatewayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            _send_json(self, 200, {"status": "ok"})
            return
        self._proxy()

    def do_POST(self):
        self._proxy()

    def _proxy(self):
        request_id = str(uuid.uuid4())
        supplied = self.headers.get("Authorization", "")
        expected = "Bearer " + self.server.api_token
        if not hmac.compare_digest(supplied, expected):
            _send_json(self, 401, {"error": "unauthorized"}, request_id)
            return

        workload = next(
            (item for item in self.server.workloads
             if self.path == item["route"] or self.path.startswith(item["route"] + "/")),
            None,
        )
        if workload is None:
            _send_json(self, 404, {"error": "route not found"}, request_id)
            return
        path = self.path[len(workload["route"]):] or "/"
        try:
            length = int(self.headers.get("Content-Length", "0")) if self.command == "POST" else 0
        except ValueError:
            _send_json(self, 400, {"error": "invalid content length"}, request_id)
            return
        if length < 0 or length > MAX_BODY_BYTES:
            _send_json(self, 413, {"error": "request body exceeds the 1 MB limit"}, request_id)
            return
        body = self.rfile.read(length) if self.command == "POST" else None
        request = urllib.request.Request(
            f"http://{workload['host']}:{workload['port']}{path}",
            data=body,
            headers={"Content-Type": self.headers.get("Content-Type", "application/json"),
                     "X-Request-Id": request_id},
            method=self.command,
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                status, response_body = response.status, response.read(MAX_BODY_BYTES + 1)
        except urllib.error.HTTPError as error:
            status, response_body = error.code, error.read(MAX_BODY_BYTES + 1)
        except (urllib.error.URLError, TimeoutError):
            status = 502
            response_body = json.dumps({"error": "workload unavailable"}).encode("utf-8")
        if len(response_body) > MAX_BODY_BYTES:
            status, response_body = 502, b'{"error":"workload response exceeds the 1 MB limit"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.send_header("X-Request-Id", request_id)
        self.end_headers()
        self.wfile.write(response_body)
        print(json.dumps({"request_id": request_id, "route": workload["route"], "status": status}), flush=True)

    def log_message(self, *_):
        pass


def _serve(handler, host, port, **attributes):
    server = ThreadingHTTPServer((host, port), handler)
    for name, value in attributes.items():
        setattr(server, name, value)
    print(f"listening on http://{host}:{port}", flush=True)
    server.serve_forever()


def _wait_for_health(host, port, process):
    url = f"http://{host}:{port}/healthz"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and process.poll() is None:
        try:
            with urllib.request.urlopen(url, timeout=0.5):
                return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.1)
    raise RuntimeError(f"service at {url} did not become healthy")


def run_local(config_path, config):
    token_env = config["gateway"]["token_env"]
    if not os.environ.get(token_env):
        raise RuntimeError(f"set {token_env} to a local demo token before starting")
    children = []
    script = str(Path(__file__).resolve())
    try:
        for workload in config["workloads"]:
            child = subprocess.Popen(
                [sys.executable, script, "workload", workload["name"], "--config", config_path]
            )
            children.append(child)
            _wait_for_health(workload["host"], workload["port"], child)
        gateway = config["gateway"]
        child = subprocess.Popen([sys.executable, script, "gateway", "--config", config_path])
        children.append(child)
        _wait_for_health(gateway["host"], gateway["port"], child)
        print(f"gateway ready at http://{gateway['host']}:{gateway['port']}", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.2)
        raise RuntimeError("a service stopped unexpectedly")
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in reversed(children):
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "run", "gateway"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", default=str(Path(__file__).with_name("platform.json")))
    workload_parser = subparsers.add_parser("workload")
    workload_parser.add_argument("name")
    workload_parser.add_argument("--config", default=str(Path(__file__).with_name("platform.json")))
    args = parser.parse_args()
    config_path = str(Path(args.config).resolve())
    config = load_config(config_path)

    if args.command == "validate":
        print(f"valid: {len(config['workloads'])} workloads")
    elif args.command == "workload":
        workload = next((item for item in config["workloads"] if item["name"] == args.name), None)
        if workload is None:
            parser.error(f"unknown workload: {args.name}")
        _serve(WorkloadHandler, workload["host"], workload["port"], workload=workload)
    elif args.command == "gateway":
        gateway = config["gateway"]
        token = os.environ.get(gateway["token_env"])
        if not token:
            raise RuntimeError(f"set {gateway['token_env']} before starting the gateway")
        _serve(GatewayHandler, gateway["host"], gateway["port"],
               workloads=config["workloads"], api_token=token)
    else:
        run_local(config_path, config)


if __name__ == "__main__":
    main()
