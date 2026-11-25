# Architecture and governance

## Flow

`examples/requirement.json` illustrates the input contract: a DNS-style service slug, title, summary, and one or more capabilities with outcomes and acceptance criteria. The CLI validates shape, field lengths, and the slug (used in generated filenames/content). Planning creates `requirement.json` and `backlog.json`, with stable epic (`E1`), story (`S1.1`), criterion (`AC1.1.1`), and task (`T1.1.1`) IDs. Each story links its criteria and tasks; `review.json` maps story/criterion IDs to generated files. The mapping is a review aid, **not** proof that arbitrary criteria have been implemented.

| Stage | Outputs | Required human decision |
| --- | --- | --- |
| `plan` | Requirement snapshot, backlog | Review scope and acceptance criteria; `approve plan` |
| `implement` | Read-only Python sample app, HTTP tests, Dockerfile | None before automated verification |
| `verify` | Test transcript and review/trace report | Check whether the fixed template actually satisfies the requirement; `approve implementation` |
| `prepare` | Kubernetes Deployment and manual GitHub Actions preparation workflow | Review image, cluster policies and release plan; `approve deployment` |

`prepare` does not publish an image, deploy, or execute the generated workflow. The sample workflow requires GitHub environment protection **if configured by an operator**; it checks a placeholder manifest only. A deployment implementation must be added after security and platform review. The sample app deliberately offers only `/health` and `/`; criteria not served by those routes require manual implementation and tests. The Docker image tag `reviewed-tag` is a placeholder, not a deployable artifact. Replace it with a reviewed immutable digest and configure registry, authentication, TLS, observability and operational policies before any production use.

## Permission and isolation model

The planner, implementer, verifier and deployment preparer are separate local stages with only the permissions needed to read the requirement, write to a **new output directory**, and (for verification) run the fixed generated test suite. No AI model, shell instructions from requirement text, network API, credentials, or privileged deployment permissions are needed. Inputs are never interpolated into executable code except for a strictly validated slug. Paths for generated files are fixed; existing output paths are not overwritten. The verification subprocess uses isolated Python mode, restricted environment, an execution timeout, and file hashes to detect changes to tracked artifacts. Tests use localhost only. For untrusted users, run the CLI and generated tests inside a separate OS/container sandbox with filesystem and network restrictions: Python isolation, checksums and human gates are **not security boundaries**.

Each stage and approval is recorded in `state.json` with UTC timestamp, action and reviewer label; SHA-256 digests of generated files and the expected artifact set for each stage are checked before further stages. This is a local, editable demonstration audit trail, **not tamper-proof attestation**: anyone who can edit `state.json` and the output can forge approvals and matching artifacts. For organizational use, send approval and artifact records to immutable audit storage, tie reviewers to authenticated identities, enforce separation of duties and require repository/environment protections. Generated workflow permissions are read-only; its image-digest check fails on the placeholder, and no production deployment action is included.

The input, example and templates are newly generated, synthetic and customer-neutral. Do not copy private meeting data, identities, proprietary code, source documents, secrets, or organization-specific infrastructure into requirements, artifacts, tests, or logs.
