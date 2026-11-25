"""Deterministic, approval-gated delivery workflow."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone


TEMPLATES = Path(__file__).parent / "templates"
SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
STAGES = {
    "plan": "planned",
    "implement": "implemented",
    "verify": "verified",
    "prepare": "prepared",
}


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event(state, action, reviewer=None):
    entry = {"action": action, "at": datetime.now(timezone.utc).isoformat()}
    if reviewer is not None:
        entry["reviewer"] = reviewer
    state["audit"].append(entry)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(requirement):
    require(isinstance(requirement, dict), "requirement must be an object")
    require(set(requirement) == {"slug", "title", "summary", "capabilities"}, "invalid requirement fields")
    slug = requirement["slug"]
    require(isinstance(slug, str) and len(slug) <= 40 and SLUG.fullmatch(slug), "invalid slug")
    for key in ("title", "summary"):
        text(requirement[key], key)
    capabilities = requirement["capabilities"]
    require(isinstance(capabilities, list) and 1 <= len(capabilities) <= 20, "capabilities must have 1-20 entries")
    for cap in capabilities:
        require(isinstance(cap, dict) and set(cap) == {"name", "outcome", "acceptance_criteria"}, "invalid capability")
        text(cap["name"], "name")
        text(cap["outcome"], "outcome")
        criteria = cap["acceptance_criteria"]
        require(isinstance(criteria, list) and 1 <= len(criteria) <= 10, "invalid acceptance criteria")
        for criterion in criteria:
            text(criterion, "acceptance criterion")


def text(value, field):
    require(isinstance(value, str) and 1 <= len(value.strip()) <= 300, f"invalid {field}")


def backlog(requirement):
    epics = []
    for index, cap in enumerate(requirement["capabilities"], 1):
        epic_id = f"E{index}"
        story_id = f"S{index}.1"
        epics.append({
            "id": epic_id,
            "title": cap["name"],
            "outcome": cap["outcome"],
            "stories": [{
                "id": story_id,
                "title": cap["name"],
                "acceptance_criteria": [
                    {"id": f"AC{index}.1.{number}", "text": criterion}
                    for number, criterion in enumerate(cap["acceptance_criteria"], 1)
                ],
                "tasks": [
                    {"id": f"T{index}.1.1", "description": "Review the service template against these criteria"},
                    {"id": f"T{index}.1.2", "description": "Implement and test the required behavior"},
                    {"id": f"T{index}.1.3", "description": "Review deployment readiness and operational controls"},
                ],
            }],
        })
    return {"requirement": requirement["slug"], "epics": epics}


def tracked(output, state, relative_paths):
    for relative in relative_paths:
        state["artifacts"][relative] = digest(output / relative)


def integrity(output, state):
    for relative, expected in state["artifacts"].items():
        path = output / relative
        require(path.is_file() and not path.is_symlink() and digest(path) == expected, f"artifact changed: {relative}")


def run(args):
    output = args.output.resolve()
    if args.command == "plan":
        source = args.requirement
        require(source.stat().st_size <= 65536, "requirement is too large")
        requirement = load(source)
        validate(requirement)
        require(not output.exists(), "output already exists; choose an empty path")
        output.mkdir(parents=True)
        save(output / "requirement.json", requirement)
        save(output / "backlog.json", backlog(requirement))
        state = {"stage": "planned", "approvals": [], "audit": [], "artifacts": {}}
        tracked(output, state, ["requirement.json", "backlog.json"])
        event(state, "plan")
    else:
        require((output / "state.json").is_file() and not (output / "state.json").is_symlink(), "run not found")
        state = load(output / "state.json")
        require(isinstance(state, dict) and state.get("stage") in STAGES.values(), "invalid run state")
        integrity(output, state)
        if args.command == "status":
            print(json.dumps({"stage": state["stage"], "approvals": state["approvals"], "artifacts": sorted(state["artifacts"])}, indent=2))
            return
        if args.command == "approve":
            expected = {"plan": "planned", "implementation": "verified", "deployment": "prepared"}[args.gate]
            require(state["stage"] == expected, f"{args.gate} approval requires {expected} stage")
            require(args.gate not in state["approvals"], "gate already approved")
            text(args.reviewer, "reviewer")
            state["approvals"].append(args.gate)
            event(state, f"approve:{args.gate}", args.reviewer.strip())
        elif args.command == "implement":
            require(state["stage"] == "planned" and "plan" in state["approvals"], "plan approval required")
            slug = load(output / "requirement.json")["slug"]
            paths = ["app.py", "tests/test_app.py", "Dockerfile"]
            for relative in paths:
                target = output / relative
                require(target.parent.resolve().is_relative_to(output) and not target.exists() and not target.is_symlink(),
                        f"unsafe output path: {relative}")
                target.parent.mkdir(parents=True, exist_ok=True)
                content = (TEMPLATES / relative).read_text(encoding="utf-8").replace("__SERVICE_SLUG__", slug)
                target.write_text(content, encoding="utf-8")
            tracked(output, state, paths)
            state["stage"] = "implemented"
            event(state, "implement")
        elif args.command == "verify":
            require(state["stage"] == "implemented", "implementation required")
            result = subprocess.run(
                [sys.executable, "-I", "-m", "unittest", "discover", "-s", "tests", "-v"],
                cwd=output, capture_output=True, text=True, timeout=30,
                env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"},
                check=False,
            )
            review = {
                "result": "passed" if result.returncode == 0 else "failed",
                "tests": result.stdout + result.stderr,
                "trace": [
                    {"story": story["id"], "acceptance_criteria": [item["id"] for item in story["acceptance_criteria"]],
                     "artifacts": ["app.py", "tests/test_app.py"]}
                    for epic in load(output / "backlog.json")["epics"] for story in epic["stories"]
                ],
                "manual_review": "Confirm generated behavior satisfies each criterion; automated tests cover only the template.",
            }
            save(output / "review.json", review)
            tracked(output, state, ["review.json"])
            require(result.returncode == 0, "generated tests failed; inspect review.json")
            state["stage"] = "verified"
            event(state, "verify")
        elif args.command == "prepare":
            require(state["stage"] == "verified" and "implementation" in state["approvals"],
                    "implementation approval required")
            slug = load(output / "requirement.json")["slug"]
            paths = ["deploy/deployment.yaml", "deploy/workflow.yml"]
            for relative in paths:
                target = output / relative
                require(target.parent.resolve().is_relative_to(output) and not target.exists() and not target.is_symlink(),
                        f"unsafe output path: {relative}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((TEMPLATES / relative).read_text(encoding="utf-8").replace("__SERVICE_SLUG__", slug),
                                  encoding="utf-8")
            tracked(output, state, paths)
            state["stage"] = "prepared"
            event(state, "prepare")
    save(output / "state.json", state)
    print(f"{args.command}: {state['stage']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "approve", "implement", "verify", "prepare", "status"):
        command = commands.add_parser(name)
        if name == "plan":
            command.add_argument("requirement", type=Path)
        if name == "approve":
            command.add_argument("gate", choices=("plan", "implementation", "deployment"))
            command.add_argument("--reviewer", required=True)
        command.add_argument("--output", type=Path, default=Path(".factory-output"))
    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
