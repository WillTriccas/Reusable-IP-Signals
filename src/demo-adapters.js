export class SyntheticRuntimeAdapter {
  constructor(statuses) {
    this.statuses = new Map(
      Object.entries(statuses).map(([id, status]) => [id, { ...status }]),
    );
  }

  getStatus(agentId) {
    const status = this.statuses.get(agentId);
    if (!status) {
      throw new RangeError(`No runtime status for agent: ${agentId}`);
    }
    return { ...status };
  }

  setEnabled(agentId, enabled) {
    const status = this.getStatus(agentId);
    const updated = { ...status, enabled };
    this.statuses.set(agentId, updated);
    return { ...updated };
  }
}

export class SyntheticHostingAdapter {
  constructor(environments) {
    this.environments = new Map(
      Object.entries(environments).map(([id, environment]) => [id, { ...environment }]),
    );
  }

  getEnvironment(agentId) {
    const environment = this.environments.get(agentId);
    return environment ? { ...environment } : null;
  }
}

export const runtime = new SyntheticRuntimeAdapter({
  "agent-summarizer": {
    enabled: true,
    health: "healthy",
    lastSeen: "2026-10-02T11:46:00Z",
  },
  "agent-release-notes": {
    enabled: true,
    health: "degraded",
    lastSeen: "2026-10-02T11:43:00Z",
  },
  "agent-metrics": {
    enabled: false,
    health: "healthy",
    lastSeen: "2026-10-02T11:39:00Z",
  },
});

export const hosting = new SyntheticHostingAdapter({
  "agent-summarizer": { name: "Sandbox Alpha", type: "Container", region: "test-region-1" },
  "agent-release-notes": { name: "Sandbox Beta", type: "Container", region: "test-region-1" },
  "agent-metrics": { name: "Sandbox Alpha", type: "Container", region: "test-region-2" },
});
