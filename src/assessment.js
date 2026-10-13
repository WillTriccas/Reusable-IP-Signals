const DAY_MS = 24 * 60 * 60 * 1000;

export const CONTROL_PATTERNS = [
  {
    id: "restrictive-defaults",
    title: "Restrictive-by-default configuration",
    blocker: "Unsafe or unspecified sharing and provider-training settings",
    implementation: "Default external sharing and provider use for training to disabled; require an approved exception to change policy.",
    evidence: "Effective policy values and change events."
  },
  {
    id: "lifecycle-ownership",
    title: "Lifecycle ownership and expiry",
    blocker: "No accountable owner, or ownership is expired",
    implementation: "Require an accepting owner and an expiry date; block continued operation when ownership expires.",
    evidence: "Owner acceptance, expiry, and renewal events."
  },
  {
    id: "attestation",
    title: "Periodic governance attestation",
    blocker: "No current, attributable attestation",
    implementation: "Collect a dated attestation from an identified reviewer on a configurable cadence.",
    evidence: "Attestation statement, reviewer, and timestamp."
  },
  {
    id: "access-recertification",
    title: "Access recertification",
    blocker: "Access has not been reviewed on schedule",
    implementation: "Review every principal periodically; explicitly retain or revoke each grant.",
    evidence: "Reviewer decision for every principal and review timestamp."
  },
  {
    id: "exception-handling",
    title: "Approved, time-bounded exceptions",
    blocker: "A policy deviation lacks a valid, attributable approval",
    implementation: "Require scope, rationale, approver, approval rationale, and expiry; never silently waive residual risk.",
    evidence: "Request and approval details, validity, and audit events."
  }
];

const PATTERN_IDS = new Set(CONTROL_PATTERNS.map(({ id }) => id));

function isDate(value) {
  return typeof value === "string" && !Number.isNaN(Date.parse(value));
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.trim() !== "";
}

function isCurrent(value, now, maxAgeDays) {
  return isDate(value) && Date.parse(value) <= now &&
    now - Date.parse(value) <= maxAgeDays * DAY_MS;
}

function validException(exception, now) {
  return exception?.status === "approved" &&
    isNonEmptyString(exception.controlId) &&
    isNonEmptyString(exception.rationale) &&
    isNonEmptyString(exception.requestedBy) &&
    isNonEmptyString(exception.approvedBy) &&
    exception.approvedBy !== exception.requestedBy &&
    isNonEmptyString(exception.approvalRationale) &&
    isDate(exception.approvedAt) && Date.parse(exception.approvedAt) <= now &&
    isDate(exception.expiresAt) && Date.parse(exception.expiresAt) > now;
}

function gap(id, reason) {
  return { id, reason };
}

export function assessCapability(profile, { now = new Date() } = {}) {
  if (!profile || typeof profile !== "object" || Array.isArray(profile)) {
    throw new TypeError("Capability profile must be a JSON object.");
  }
  if (!isNonEmptyString(profile.id)) {
    throw new TypeError("Capability profile must include a non-empty id.");
  }

  const timestamp = new Date(now).getTime();
  if (Number.isNaN(timestamp)) throw new TypeError("Assessment time must be a valid date.");

  const gaps = [];
  if (profile.policy?.externalSharing !== false || profile.policy?.providerTraining !== false) {
    gaps.push(gap("restrictive-defaults", "External sharing and provider training must both be explicitly disabled."));
  }
  if (
    !isNonEmptyString(profile.owner?.id) ||
    !isDate(profile.owner?.expiresAt) ||
    Date.parse(profile.owner.expiresAt) <= timestamp
  ) {
    gaps.push(gap("lifecycle-ownership", "An accepting owner with a future expiry date is required."));
  }
  if (
    profile.attestation?.status !== "attested" ||
    !isNonEmptyString(profile.attestation.reviewer) ||
    !isNonEmptyString(profile.attestation.statement) ||
    !isCurrent(profile.attestation.attestedAt, timestamp, profile.attestation.maxAgeDays ?? 365)
  ) {
    gaps.push(gap("attestation", "A current, attributable governance attestation is required."));
  }
  if (
    !isCurrent(profile.accessReview?.reviewedAt, timestamp, profile.accessReview?.maxAgeDays ?? 90) ||
    !isNonEmptyString(profile.accessReview?.reviewer) ||
    !Array.isArray(profile.accessReview?.members) ||
    profile.accessReview.members.some((member) => !["retain", "revoke"].includes(member?.decision))
  ) {
    gaps.push(gap("access-recertification", "A current review with an explicit decision for every access grant is required."));
  }

  const exception = profile.exception;
  if (exception && exception.status !== "pending" && !validException(exception, timestamp)) {
    gaps.push(gap("exception-handling", "The exception is not valid: approval evidence or a future expiry is missing."));
  }
  if (exception?.status === "pending") {
    gaps.push(gap("exception-handling", "The requested exception has not been approved."));
  }

  const exceptions = exception && validException(exception, timestamp)
    ? [{ controlId: exception.controlId, rationale: exception.rationale, expiresAt: exception.expiresAt }]
    : [];
  const controls = [...new Set(gaps.map(({ id }) => id))].map((id) =>
    CONTROL_PATTERNS.find((pattern) => pattern.id === id)
  );
  return {
    capability: { id: profile.id, name: profile.name ?? profile.id },
    assessedAt: new Date(timestamp).toISOString(),
    gaps,
    matchedControls: controls,
    approvedExceptions: exceptions,
    residualRisk: exceptions.length > 0
      ? "Approved exceptions are time-bounded deviations; they do not remove the underlying control gap."
      : null
  };
}

export function runControlWorkflow(profile, { now = new Date(), actor = "synthetic-control-runner" } = {}) {
  const timestamp = new Date(now).getTime();
  if (Number.isNaN(timestamp)) throw new TypeError("Workflow time must be a valid date.");
  if (!isNonEmptyString(actor)) throw new TypeError("Workflow actor is required.");

  const initialAssessment = assessCapability(profile, { now: timestamp });
  const working = structuredClone(profile);
  const auditTrail = [];
  const record = (action, target, details, eventActor = actor) => {
    auditTrail.push({
      sequence: auditTrail.length + 1,
      at: new Date(timestamp).toISOString(),
      actor: eventActor,
      action,
      target,
      details
    });
  };

  const beforePolicy = { ...working.policy };
  working.policy = {
    ...working.policy,
    externalSharing: false,
    providerTraining: false
  };
  record("restrictive-defaults.enforced", working.id, {
    before: beforePolicy,
    effective: working.policy
  });

  if (working.owner?.id && isDate(working.owner.expiresAt) && Date.parse(working.owner.expiresAt) <= timestamp) {
    record("ownership.expired", working.id, { ownerId: working.owner.id }, working.owner.id);
  }
  const renewal = working.workflow?.ownershipAcceptance;
  if (renewal && isNonEmptyString(renewal.ownerId) && isDate(renewal.expiresAt) && Date.parse(renewal.expiresAt) > timestamp) {
    working.owner = { id: renewal.ownerId, expiresAt: renewal.expiresAt };
    record("ownership.accepted", working.id, { expiresAt: renewal.expiresAt }, renewal.ownerId);
  }

  const attestation = working.workflow?.attestation;
  if (attestation && isNonEmptyString(attestation.reviewer) && isNonEmptyString(attestation.statement) && isDate(attestation.attestedAt)) {
    working.attestation = {
      status: "attested",
      reviewer: attestation.reviewer,
      statement: attestation.statement,
      attestedAt: attestation.attestedAt,
      maxAgeDays: attestation.maxAgeDays ?? 365
    };
    record("attestation.recorded", working.id, {
      statement: attestation.statement,
      attestedAt: attestation.attestedAt
    }, attestation.reviewer);
  }

  const accessReview = working.workflow?.accessReview;
  if (Array.isArray(accessReview?.members) && isDate(accessReview.reviewedAt) && isNonEmptyString(accessReview.reviewer)) {
    const complete = accessReview.members.every((member) => ["retain", "revoke"].includes(member?.decision));
    if (complete) {
      working.accessReview = {
        reviewer: accessReview.reviewer,
        reviewedAt: accessReview.reviewedAt,
        maxAgeDays: accessReview.maxAgeDays ?? 90,
        members: accessReview.members
      };
      for (const member of accessReview.members) {
        const action = member.decision === "retain" ? "access.retained" : "access.revoked";
        record(action, member.principal, { reviewedAt: accessReview.reviewedAt }, accessReview.reviewer ?? actor);
      }
      record("access.review.completed", working.id, { reviewedAt: accessReview.reviewedAt }, accessReview.reviewer ?? actor);
    }
  }

  const exception = working.exception;
  if (exception?.status === "pending") {
    record("exception.requested", exception.controlId, {
      rationale: exception.rationale,
      expiresAt: exception.expiresAt
    }, isNonEmptyString(exception.requestedBy) ? exception.requestedBy : actor);
    const approval = working.workflow?.exceptionApproval;
    if (
      isNonEmptyString(approval?.approvedBy) &&
      approval.approvedBy !== exception.requestedBy &&
      isNonEmptyString(approval.approvalRationale) &&
      isDate(approval.approvedAt) &&
      Date.parse(approval.approvedAt) <= timestamp &&
      isDate(exception.expiresAt) &&
      Date.parse(exception.expiresAt) > timestamp
    ) {
      working.exception = {
        ...exception,
        status: "approved",
        approvedBy: approval.approvedBy,
        approvalRationale: approval.approvalRationale,
        approvedAt: approval.approvedAt
      };
      record("exception.approved", exception.controlId, {
        rationale: exception.rationale,
        approvalRationale: approval.approvalRationale,
        expiresAt: exception.expiresAt
      }, approval.approvedBy);
    }
  } else if (validException(exception, timestamp)) {
    record("exception.approval-recorded", exception.controlId, {
      rationale: exception.rationale,
      approvalRationale: exception.approvalRationale,
      expiresAt: exception.expiresAt
    }, exception.approvedBy);
  }

  return {
    initialAssessment,
    finalAssessment: assessCapability(working, { now: timestamp }),
    effectiveProfile: working,
    auditTrail
  };
}

export function getControlPattern(id) {
  if (!PATTERN_IDS.has(id)) return undefined;
  return CONTROL_PATTERNS.find((pattern) => pattern.id === id);
}
