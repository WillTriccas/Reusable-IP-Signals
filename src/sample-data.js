export const agents = [
  {
    id: "agent-summarizer",
    name: "Document Summarizer",
    description: "Creates concise summaries from submitted documents.",
    runtime: { name: "Sample Runtime", version: "1.2" },
    policy: {
      policyId: "policy-standard-reviewed",
      approvalRequired: true,
      approved: true,
      dataClassification: "Internal",
    },
  },
  {
    id: "agent-release-notes",
    name: "Release Note Assistant",
    description: "Drafts release notes from synthetic change summaries.",
    runtime: { name: "Sample Runtime", version: "1.2" },
    policy: {
      policyId: "policy-standard-reviewed",
      approvalRequired: true,
      approved: true,
      dataClassification: "Public",
    },
  },
  {
    id: "agent-metrics",
    name: "Metrics Analyst",
    description: "Explains synthetic service metrics and trends.",
    runtime: { name: "Sample Runtime", version: "2.0" },
    policy: {
      policyId: "policy-pending-review",
      approvalRequired: true,
      approved: false,
      dataClassification: "Internal",
    },
  },
];
