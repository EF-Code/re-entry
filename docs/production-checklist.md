# Production readiness checklist

This is the hand-off list for turning the demo into a real AgentCore workload.
Items marked **done locally** describe code in this repository; they are not a
claim that AWS infrastructure has been deployed.

| Area | State | Next evidence |
| --- | --- | --- |
| Strands orchestration | **done locally** | `strands.Agent` with deterministic offline model; Bedrock adapter behind `REENTRY_MODE=live` |
| Human approval boundary | **done locally** | `needs_approval` actions cannot be approved by the planner; approvals bind to a case revision, and audit marks demo caller labels unverified |
| Untrusted document handling | **done locally** | Bounded pre-parser, incremental upload hashing, upload size, extension, path/control-character checks, per-case cap, and quarantine tests |
| Safe provider failures | **done locally** | Live-mode exceptions fall back without exposing internals |
| Container artifact | **done locally** | Digest-pinned multi-stage image; amd64/ARM64 builds, health smoke, non-root runtime, and ~89 MB local image size |
| Bedrock model configuration | **done locally** | Live adapter defaults to the current US Claude Sonnet 4.5 geo inference profile and keeps an explicit 1,200-token cap |
| Authentication | pending | AgentCore IAM or CUSTOM_JWT; never `NONE` |
| IAM scoping | pending | Exact Bedrock model ARN, ECR repository, and account-scoped trust policy |
| Outbound credentials | pending | AgentCore Gateway targets / credential providers; no secrets in runtime env |
| Durable data | **guarded locally** | Live readiness rejects the process-local store by default; encrypted S3 objects, DynamoDB case graph, retention and deletion policy still required |
| Rate limiting | **partial locally** | Non-resettable live per-case plan budget and in-process per-case serialization; API Gateway/application per-user and per-tenant limits still required |
| Observability | pending | X-Ray, CloudWatch retention, connector receipts and alerting |
| Quality baseline | pending | Representative cases, refusal tests, prompt-injection tests, goal-success eval |
| Deployment | pending | AgentCore CLI/runtime config, ARM64 image, authorizer, and a verified public test URL |

The local `agentcore` CLI is now installed at v0.29.0 and the repository includes
an HTTP BYO-container spec under `agentcore/`. The account-specific
`aws-targets.json`, AWS CLI credentials, runtime ARN, IAM receipt, and public
AgentCore endpoint are still absent. No cloud deployment is claimed. Run
`scripts/agentcore-preflight.sh` after configuring a target; it refuses to
continue without an AWS identity and a valid ARM64 Dockerfile check.
