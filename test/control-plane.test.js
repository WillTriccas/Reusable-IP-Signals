import test from "node:test";
import assert from "node:assert/strict";
import { AgentControlPlane, PolicyViolationError } from "../src/control-plane.js";
import { SyntheticHostingAdapter, SyntheticRuntimeAdapter } from "../src/demo-adapters.js";
import { agents } from "../src/sample-data.js";

function createControlPlane() {
  const runtime = new SyntheticRuntimeAdapter({
    "agent-summarizer": { enabled: true, health: "healthy", lastSeen: "2026-10-02T11:46:00Z" },
    "agent-release-notes": { enabled: true, health: "degraded", lastSeen: "2026-10-02T11:43:00Z" },
    "agent-metrics": { enabled: false, health: "healthy", lastSeen: "2026-10-02T11:39:00Z" },
  });
  const hosting = new SyntheticHostingAdapter({
    "agent-summarizer": { name: "Sandbox Alpha", type: "Container", region: "test-region-1" },
    "agent-release-notes": { name: "Sandbox Beta", type: "Container", region: "test-region-1" },
    "agent-metrics": { name: "Sandbox Alpha", type: "Container", region: "test-region-2" },
  });
  return { controlPlane: new AgentControlPlane({ agents, runtime, hosting }), runtime };
}

test("lists inventory with runtime health, lifecycle state, and hosting metadata", () => {
  const { controlPlane } = createControlPlane();
  const inventory = controlPlane.listAgents();

  assert.equal(inventory.length, 3);
  assert.equal(inventory[0].health, "healthy");
  assert.equal(inventory[0].enabled, true);
  assert.deepEqual(inventory[0].environment, {
    name: "Sandbox Alpha",
    type: "Container",
    region: "test-region-1",
  });
  assert.equal(inventory[2].policy.approved, false);
});

test("enables and disables approved agents through the runtime adapter", () => {
  const { controlPlane, runtime } = createControlPlane();

  assert.equal(controlPlane.setEnabled("agent-summarizer", false).enabled, false);
  assert.equal(runtime.getStatus("agent-summarizer").enabled, false);
  assert.equal(controlPlane.setEnabled("agent-summarizer", true).enabled, true);
});

test("blocks enabling an agent that has not received required approval", () => {
  const { controlPlane, runtime } = createControlPlane();

  assert.throws(
    () => controlPlane.setEnabled("agent-metrics", true),
    PolicyViolationError,
  );
  assert.equal(runtime.getStatus("agent-metrics").enabled, false);
});

test("rejects unknown agents and non-boolean lifecycle requests", () => {
  const { controlPlane } = createControlPlane();

  assert.throws(() => controlPlane.setEnabled("missing-agent", false), RangeError);
  assert.throws(() => controlPlane.setEnabled("agent-summarizer", "false"), TypeError);
});

test("returns copies so callers cannot mutate the catalog through inventory results", () => {
  const { controlPlane } = createControlPlane();
  const inventory = controlPlane.listAgents();
  inventory[0].policy.approved = false;
  inventory[0].environment.name = "Changed";

  const refreshed = controlPlane.listAgents()[0];
  assert.equal(refreshed.policy.approved, true);
  assert.equal(refreshed.environment.name, "Sandbox Alpha");
});
