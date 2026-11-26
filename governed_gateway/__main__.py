"""Run a synthetic scenario and emit decisions and telemetry as JSON."""

import argparse
import json

from . import Gateway, MockProvider, Model, Policy, Principal, Request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", help="path to a synthetic JSON scenario")
    args = parser.parse_args()
    with open(args.scenario, encoding="utf-8") as source:
        scenario = json.load(source)
    config = scenario["policy"]
    policy = Policy(
        routes={task: tuple(models) for task, models in config["routes"].items()},
        allowed_roles=frozenset(config["allowed_roles"]),
        sensitive_action=config.get("sensitive_action", "redact"),
        max_input_units=config.get("max_input_units", 100),
        max_output_units=config.get("max_output_units", 20),
        rate_limit=config.get("rate_limit", 10),
        rate_window_seconds=config.get("rate_window_seconds", 60),
    )
    principals = [
        Principal(item["name"], frozenset(item["roles"]), item["budget_microcredits"])
        for item in scenario["principals"]
    ]
    providers = {name: MockProvider(fail=fail) for name, fail in scenario["providers"].items()}
    gateway = Gateway(policy, principals, providers)
    for model in scenario["models"]:
        gateway.propose_model(Model(**model))
    results = []
    for action in scenario["actions"]:
        if action["type"] == "approve":
            gateway.approve_model(action["model"], action["approver"])
        elif action["type"] == "revoke":
            gateway.revoke_access(action["principal"])
        elif action["type"] == "request":
            results.append(gateway.handle(Request(action["principal"], action["task"], action["prompt"])))
        else:
            raise ValueError("unknown scenario action")
    print(json.dumps({"results": results, "telemetry": gateway.telemetry, "spend_microcredits": dict(gateway.spend)}, indent=2))


if __name__ == "__main__":
    main()
