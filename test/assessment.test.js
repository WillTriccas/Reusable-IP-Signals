import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { assessCapability, CONTROL_PATTERNS, runControlWorkflow } from "../src/assessment.js";

const now = new Date("2026-10-13T12:00:00Z");
const baseProfile = {
  id: "synthetic-01",
  policy: { externalSharing: false, providerTraining: false },
  owner: { id: "synthetic-owner", expiresAt: "2027-01-01T00:00:00Z" },
  attestation: {
    status: "attested",
    reviewer: "synthetic-reviewer",
    statement: "Synthetic test attestation",
    attestedAt: "2026-10-01T00:00:00Z"
  },
  accessReview: {
    reviewer: "synthetic-reviewer",
    reviewedAt: "2026-10-01T00:00:00Z",
    members: [{ principal: "synthetic-user", decision: "retain" }]
  }
};

test("assessment maps each missing control to a reusable pattern", () => {
  const report = assessCapability({ id: "synthetic-02" }, { now });
  assert.deepEqual(report.gaps.map(({ id }) => id), [
    "restrictive-defaults",
    "lifecycle-ownership",
    "attestation",
    "access-recertification"
  ]);
  assert.deepEqual(report.matchedControls.map(({ id }) => id), report.gaps.map(({ id }) => id));
  assert.equal(CONTROL_PATTERNS.length, 5);
});

test("current evidence passes and expired, incomplete or future evidence does not", () => {
  assert.deepEqual(assessCapability(baseProfile, { now }).gaps, []);
  const profile = structuredClone(baseProfile);
  profile.owner.expiresAt = "2026-10-13T11:59:59Z";
  profile.attestation.attestedAt = "2027-01-01T00:00:00Z";
  profile.accessReview.members[0] = null;
  assert.deepEqual(
    assessCapability(profile, { now }).gaps.map(({ id }) => id),
    ["lifecycle-ownership", "attestation", "access-recertification"]
  );
});

test("only complete, unexpired approved exceptions are reported and never erase the underlying gap", () => {
  const profile = {
    ...baseProfile,
    policy: { externalSharing: true, providerTraining: false },
    exception: {
      status: "approved",
      controlId: "external-sharing",
      rationale: "Synthetic limited scope",
      requestedBy: "synthetic-requester",
      approvedBy: "synthetic-approver",
      approvalRationale: "Synthetic approval record",
      approvedAt: "2026-10-01T00:00:00Z",
      expiresAt: "2026-12-01T00:00:00Z"
    }
  };
  const report = assessCapability(profile, { now });
  assert.deepEqual(report.gaps.map(({ id }) => id), ["restrictive-defaults"]);
  assert.equal(report.approvedExceptions.length, 1);
  assert.match(report.residualRisk, /do not remove/);

  profile.exception.expiresAt = "2026-01-01T00:00:00Z";
  assert.deepEqual(
    assessCapability(profile, { now }).gaps.map(({ id }) => id),
    ["restrictive-defaults", "exception-handling"]
  );
});

test("workflow enforces restrictive defaults and records expiry, ownership, attestations, access, exceptions", async () => {
  const profile = JSON.parse(await readFile(new URL("../examples/synthetic-profile.json", import.meta.url)));
  const result = runControlWorkflow(profile, { now, actor: "synthetic-operator" });
  const actions = result.auditTrail.map(({ action }) => action);

  assert.deepEqual(result.effectiveProfile.policy, {
    externalSharing: false,
    providerTraining: false
  });
  assert.ok(actions.includes("ownership.expired"));
  assert.ok(actions.includes("ownership.accepted"));
  assert.ok(actions.includes("attestation.recorded"));
  assert.ok(actions.includes("access.retained"));
  assert.ok(actions.includes("access.revoked"));
  assert.ok(actions.includes("access.review.completed"));
  assert.ok(actions.includes("exception.requested"));
  assert.ok(actions.includes("exception.approved"));
  assert.deepEqual(result.finalAssessment.gaps, []);
  assert.equal(result.finalAssessment.approvedExceptions.length, 1);
  assert.equal(profile.policy.externalSharing, true, "workflow must not mutate its input");
  assert.deepEqual(result.auditTrail.map(({ sequence }) => sequence), [1, 2, 3, 4, 5, 6, 7, 8, 9]);
  assert.ok(result.initialAssessment.gaps.some(({ id }) => id === "exception-handling"));
});

test("exception workflow does not allow self-approval or approval dated in the future", async () => {
  const profile = JSON.parse(await readFile(new URL("../examples/synthetic-profile.json", import.meta.url)));
  profile.workflow.exceptionApproval.approvedBy = profile.exception.requestedBy;
  profile.workflow.exceptionApproval.approvedAt = "2027-01-01T00:00:00Z";
  const result = runControlWorkflow(profile, { now });
  assert.equal(result.effectiveProfile.exception.status, "pending");
  assert.ok(result.finalAssessment.gaps.some(({ id }) => id === "exception-handling"));
  assert.ok(!result.auditTrail.some(({ action }) => action === "exception.approved"));
});

test("invalid profiles, dates, and workflow actors are rejected", () => {
  assert.throws(() => assessCapability(null, { now }), /JSON object/);
  assert.throws(() => assessCapability({ id: "x" }, { now: "not-a-date" }), /valid date/);
  assert.throws(() => runControlWorkflow(baseProfile, { now, actor: "" }), /actor is required/);
});
