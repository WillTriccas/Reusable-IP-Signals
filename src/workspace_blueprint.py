#!/usr/bin/env python3
"""Validate workspace policy and normalize privacy-conscious telemetry."""

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "workspace-policy.json"
WORKSPACE_TYPES = {"local", "cloud", "ephemeral"}
ACTOR_TYPES = {"engineer", "agent", "collaborator"}
OUTCOMES = {"allowed", "denied", "success", "failure"}
SAFE_ATTRIBUTES = {"model_id", "policy_reason", "tool_name", "cost_microunits"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
MAX_SAFE_INTEGER = 9007199254740991


def validate_config(config):
    if (
        not isinstance(config, dict)
        or type(config.get("version")) is not int
        or config["version"] != 1
    ):
        raise ValueError("configuration version must be 1")
    if not isinstance(config.get("policy_revision"), str) or not config["policy_revision"]:
        raise ValueError("policy_revision must identify the reviewed policy")

    enablement = config.get("enablement")
    if not isinstance(enablement, dict):
        raise ValueError("enablement must be an object")
    stages = enablement.get("stages")
    if (
        not isinstance(stages, list)
        or not stages
        or any(not isinstance(stage, str) or not stage for stage in stages)
        or len(set(stages)) != len(stages)
    ):
        raise ValueError("enablement.stages must be a non-empty list of unique names")
    if enablement.get("default_stage") not in stages:
        raise ValueError("enablement.default_stage must be a configured stage")
    group_stages = enablement.get("group_stages")
    if not isinstance(group_stages, dict) or not group_stages:
        raise ValueError("enablement.group_stages must map groups to stages")
    for group, group_stage_list in group_stages.items():
        if (
            not isinstance(group, str)
            or not IDENTIFIER.fullmatch(group)
            or not isinstance(group_stage_list, list)
            or not group_stage_list
            or any(
                not isinstance(group_stage, str) or group_stage not in stages
                for group_stage in group_stage_list
            )
        ):
            raise ValueError("enablement.group_stages must use configured stages")

    workspaces = config.get("workspaces")
    if not isinstance(workspaces, dict) or not WORKSPACE_TYPES.issubset(workspaces):
        raise ValueError("workspaces must define local, cloud, and ephemeral profiles")
    for workspace_type in WORKSPACE_TYPES:
        profile = workspaces[workspace_type]
        if (
            not isinstance(profile, dict)
            or not isinstance(profile.get("isolation"), str)
            or not profile["isolation"].strip()
        ):
            raise ValueError("each workspace profile must declare isolation")
        network = profile.get("network")
        if not isinstance(network, dict) or network.get("default") != "deny":
            raise ValueError("each workspace network policy must default to deny")
        allowed_destinations = network.get("allow")
        if not isinstance(allowed_destinations, list) or any(
            not isinstance(destination, str) or not destination
            for destination in allowed_destinations
        ):
            raise ValueError("workspace network allow must be a list of destination names")

    model_policy = config.get("model_policy")
    if not isinstance(model_policy, dict) or model_policy.get("default") != "deny":
        raise ValueError("model_policy must default to deny")
    models = model_policy.get("models")
    if not isinstance(models, list):
        raise ValueError("model_policy.models must be a list")
    model_ids = set()
    for model in models:
        if not isinstance(model, dict):
            raise ValueError("each model policy entry must be an object")
        model_id = model.get("id")
        if not isinstance(model_id, str) or not model_id or model_id in model_ids:
            raise ValueError("model policy ids must be unique non-empty strings")
        model_ids.add(model_id)
        for key in ("stages", "groups", "data_classifications"):
            values = model.get(key)
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                raise ValueError("model policy {} must be a list of names".format(key))
        if not set(model["stages"]).issubset(stages):
            raise ValueError("model policy stages must be configured enablement stages")
        if not set(model["groups"]).issubset(group_stages):
            raise ValueError("model policy groups must be configured enablement groups")

    telemetry = config.get("telemetry")
    if (
        not isinstance(telemetry, dict)
        or not isinstance(telemetry.get("schema_version"), str)
        or not telemetry["schema_version"]
        or telemetry.get("include_prompt_content") is not False
        or telemetry.get("include_code_content") is not False
    ):
        raise ValueError("telemetry must define a schema version and exclude prompt/code content")
    return config


def load_config(path):
    with open(path, encoding="utf-8") as policy_file:
        return validate_config(json.load(policy_file))


def authorize_model(config, stage, group, model_id, classification):
    stages = config["enablement"]["stages"]
    if stage not in stages:
        reason = "stage_not_configured"
    elif stage not in config["enablement"]["group_stages"].get(group, []):
        reason = "group_not_enabled_for_stage"
    else:
        model = next(
            (entry for entry in config["model_policy"]["models"] if entry["id"] == model_id),
            None,
        )
        if model is None:
            reason = "model_not_approved"
        elif stage not in model["stages"]:
            reason = "stage_not_approved"
        elif group not in model["groups"]:
            reason = "group_not_approved"
        elif classification not in model["data_classifications"]:
            reason = "classification_not_approved"
        else:
            reason = "approved"
    return {
        "allowed": reason == "approved",
        "policy_revision": config["policy_revision"],
        "reason": reason,
    }


def normalize_event(event, schema_version="1.0"):
    if not isinstance(event, dict):
        raise ValueError("event must be a JSON object")
    normalized = {"schema_version": schema_version}
    for field in (
        "timestamp",
        "workspace_id",
        "workspace_type",
        "actor_type",
        "event_type",
        "outcome",
    ):
        value = event.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError("{} must be a non-empty string".format(field))
        normalized[field] = value
    for field in ("workspace_id", "event_type"):
        if not IDENTIFIER.fullmatch(normalized[field]):
            raise ValueError("{} must be a simple identifier".format(field))

    try:
        timestamp = datetime.fromisoformat(normalized["timestamp"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("timestamp must be ISO-8601") from error
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    if normalized["workspace_type"] not in WORKSPACE_TYPES:
        raise ValueError("workspace_type must be local, cloud, or ephemeral")
    if normalized["actor_type"] not in ACTOR_TYPES:
        raise ValueError("actor_type must be engineer, agent, or collaborator")
    if normalized["outcome"] not in OUTCOMES:
        raise ValueError("outcome must be allowed, denied, success, or failure")

    if "duration_ms" in event:
        duration = event["duration_ms"]
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or (isinstance(duration, int) and duration > MAX_SAFE_INTEGER)
            or (isinstance(duration, float) and not math.isfinite(duration))
            or duration < 0
        ):
            raise ValueError("duration_ms must be a non-negative number")
        normalized["duration_ms"] = duration

    attributes = event.get("attributes", {})
    if not isinstance(attributes, dict):
        raise ValueError("attributes must be an object")
    safe_attributes = {}
    for key in SAFE_ATTRIBUTES:
        value = attributes.get(key)
        if isinstance(value, str) and IDENTIFIER.fullmatch(value):
            safe_attributes[key] = value
        elif key == "cost_microunits" and isinstance(value, int) and not isinstance(value, bool):
            if 0 <= value <= MAX_SAFE_INTEGER:
                safe_attributes[key] = value
        elif key in attributes and value is not None:
            raise ValueError("attribute {} has an invalid value".format(key))
    if safe_attributes:
        normalized["attributes"] = safe_attributes
    return normalized


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate the workspace policy")

    authorize_parser = subparsers.add_parser("authorize", help="evaluate model policy")
    authorize_parser.add_argument("--stage", required=True)
    authorize_parser.add_argument("--group", required=True)
    authorize_parser.add_argument("--model", required=True)
    authorize_parser.add_argument("--classification", required=True)

    subparsers.add_parser("normalize-event", help="normalize one JSON event from standard input")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "validate":
            result = {
                "valid": True,
                "policy_revision": config["policy_revision"],
                "version": config["version"],
            }
        elif args.command == "authorize":
            result = authorize_model(
                config, args.stage, args.group, args.model, args.classification
            )
        else:
            event = json.load(sys.stdin)
            result = normalize_event(event, config["telemetry"]["schema_version"])
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
