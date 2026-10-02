export class PolicyViolationError extends Error {
  constructor(agentId) {
    super(`Agent "${agentId}" requires policy approval before it can be enabled.`);
    this.name = "PolicyViolationError";
    this.agentId = agentId;
  }
}

export class AgentControlPlane {
  constructor({ agents, runtime, hosting }) {
    if (!Array.isArray(agents)) {
      throw new TypeError("agents must be an array");
    }
    if (typeof runtime?.getStatus !== "function" || typeof runtime?.setEnabled !== "function") {
      throw new TypeError("runtime must implement getStatus and setEnabled");
    }
    if (typeof hosting?.getEnvironment !== "function") {
      throw new TypeError("hosting must implement getEnvironment");
    }

    this.agents = agents.map((agent) => structuredClone(agent));
    this.runtime = runtime;
    this.hosting = hosting;
  }

  listAgents() {
    return this.agents.map((agent) => ({
      ...structuredClone(agent),
      ...this.runtime.getStatus(agent.id),
      environment: this.hosting.getEnvironment(agent.id),
    }));
  }

  setEnabled(agentId, enabled) {
    if (typeof enabled !== "boolean") {
      throw new TypeError("enabled must be a boolean");
    }

    const agent = this.agents.find((item) => item.id === agentId);
    if (!agent) {
      throw new RangeError(`Unknown agent: ${agentId}`);
    }
    if (enabled && agent.policy.approvalRequired && !agent.policy.approved) {
      throw new PolicyViolationError(agentId);
    }

    this.runtime.setEnabled(agentId, enabled);
    return this.listAgents().find((item) => item.id === agentId);
  }
}
