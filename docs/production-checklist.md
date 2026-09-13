# Production readiness checklist

This is the hand-off list for turning the demo into a real AgentCore workload.
Items marked **done locally** describe code in this repository; they are not a
claim that AWS infrastructure has been deployed.

| Area | State | Next evidence |
| --- | --- | --- |
| Strands orchestration | **done locally** | `strands.Agent` with deterministic offline model; Bedrock adapter behind `REENTRY_MODE=live` |
| Human approval boundary | **done locally** | `needs_approval` actions cannot be approved by the planner and record citations/audit |
| Untrusted document handling | **done locally** | Bounded pre-parser, upload size, extension, path/control-character checks, per-case cap, and quarantine tests |
| Safe provider failures | **done locally** | Live-mode exceptions fall back without exposing internals |
| Authentication | pending | AgentCore IAM or CUSTOM_JWT; never `NONE` |
| IAM scoping | pending | Exact Bedrock model ARN, ECR repository, and account-scoped trust policy |
| Outbound credentials | pending | AgentCore Gateway targets / credential providers; no secrets in runtime env |
| Durable data | pending | Encrypted S3 objects, DynamoDB case graph, retention and deletion policy |
| Rate limiting | pending | API Gateway/application per-user and per-tenant limits |
| Observability | pending | X-Ray, CloudWatch retention, connector receipts and alerting |
| Quality baseline | pending | Representative cases, refusal tests, prompt-injection tests, goal-success eval |
| Deployment | pending | AgentCore CLI/runtime config, ARM64 image, authorizer, and a verified public test URL |

The local `agentcore` CLI is now installed at v0.29.0, but this repository has
no `agentcore/agentcore.json`, AWS CLI credentials, runtime ARN, IAM receipt,
or public AgentCore endpoint. No cloud deployment is claimed. The documented
`docker buildx --platform linux/arm64` preflight must also be run on a builder
with ARM64 support before an image is published.
