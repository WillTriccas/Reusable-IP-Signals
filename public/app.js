import { AgentControlPlane } from "/src/control-plane.js";
import { hosting, runtime } from "/src/demo-adapters.js";
import { agents } from "/src/sample-data.js";

const controlPlane = new AgentControlPlane({ agents, runtime, hosting });
const rows = document.querySelector("#agent-rows");
const notice = document.querySelector("#notice");

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function render() {
  const inventory = controlPlane.listAgents();
  const enabledCount = inventory.filter((agent) => agent.enabled).length;
  const attentionCount = inventory.filter(
    (agent) => agent.health !== "healthy" || (agent.policy.approvalRequired && !agent.policy.approved),
  ).length;

  document.querySelector("#total-count").textContent = inventory.length;
  document.querySelector("#enabled-count").textContent = enabledCount;
  document.querySelector("#attention-count").textContent = attentionCount;
  document.querySelector("#inventory-count").textContent = `${inventory.length} agents`;
  rows.innerHTML = inventory.map((agent) => {
    const blocked = !agent.enabled && agent.policy.approvalRequired && !agent.policy.approved;
    const action = agent.enabled ? "Disable" : "Enable";
    return `
      <tr>
        <td>
          <span class="agent-name">${escapeHTML(agent.name)}</span>
          <span class="agent-description">${escapeHTML(agent.description)}</span>
        </td>
        <td>
          <span class="health health-${escapeHTML(agent.health)}">${escapeHTML(agent.health)}</span>
          <span class="agent-meta">${escapeHTML(agent.runtime.name)} ${escapeHTML(agent.runtime.version)}</span>
        </td>
        <td>
          <span class="policy-state ${agent.policy.approved ? "policy-approved" : "policy-pending"}">${agent.policy.approved ? "Approved" : "Approval required"}</span>
          <span class="policy-id">${escapeHTML(agent.policy.policyId)} · ${escapeHTML(agent.policy.dataClassification)}</span>
        </td>
        <td>
          <span>${escapeHTML(agent.environment?.name ?? "Unavailable")}</span>
          <span class="agent-meta">${escapeHTML(agent.environment?.type ?? "—")} · ${escapeHTML(agent.environment?.region ?? "—")}</span>
        </td>
        <td><span class="lifecycle lifecycle-${agent.enabled ? "enabled" : "disabled"}">${agent.enabled ? "Enabled" : "Disabled"}</span></td>
        <td>
          <button class="action-button" type="button" data-agent-id="${escapeHTML(agent.id)}" data-enabled="${!agent.enabled}" ${blocked ? 'disabled title="Policy approval is required before enabling this agent."' : ""}>${action}</button>
        </td>
      </tr>`;
  }).join("");
}

rows.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-agent-id]");
  if (!button) return;
  try {
    controlPlane.setEnabled(button.dataset.agentId, button.dataset.enabled === "true");
    notice.textContent = "";
    notice.classList.remove("visible");
    render();
  } catch (error) {
    notice.textContent = error.message;
    notice.classList.add("visible");
  }
});

render();
