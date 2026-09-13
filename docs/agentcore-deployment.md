# AgentCore deployment path

The repository includes a checked-in AgentCore project spec at
`agentcore/agentcore.json`. It describes the existing FastAPI service as a
BYO-container HTTP runtime:

- `/health` and `/ping` are readiness endpoints on port 8080.
- `POST /invocations` is the plan-only runtime contract.
- Inbound authorization is `AWS_IAM`; there is no unauthenticated production
  configuration.
- OTel is enabled and short request/reply session lifetimes are explicit.
- The local runtime disables interactive docs/OpenAPI, rejects slow or
  over-limit request bodies before parsing, and keeps demo reset/rejection
  routes unavailable when `REENTRY_MODE=live`.

The committed values intentionally use `REENTRY_MODE=demo` and synthetic case
data. Do not switch to live mode until durable storage, an approved Bedrock
model, a region/model allowlist, and connector policies have been provisioned.
Live planning also requires an explicit decision about whether any
`needs_review` evidence may leave the runtime; the safe default is to exclude
it (`REENTRY_LIVE_ALLOW_UNREVIEWED_DATA=false`).

## Preflight

Install AWS CLI v2, configure an AWS identity, and create the ignored target
file from the example:

```bash
cp agentcore/aws-targets.example.json agentcore/aws-targets.json
# edit the account and region; keep this file local
./scripts/agentcore-preflight.sh
```

The preflight verifies the CLI, Docker Buildx ARM64 support, AWS identity,
target account shape, runtime protocol/auth/lifecycle invariants, source files,
and the ARM64 Dockerfile check. It never creates or updates AWS resources.

## Deployment gates

Before `agentcore deploy`, obtain evidence for each pending item in
[`production-checklist.md`](production-checklist.md):

1. Scope the execution role to the exact Bedrock model ARN, ECR repository, and
   account-scoped AgentCore trust conditions.
2. Keep `AWS_IAM` (or configure a validated `CUSTOM_JWT` discovery URL,
   audience/client, and scopes); never use `NONE`.
3. Move case state and uploaded objects to encrypted DynamoDB/S3 with a
   retention/deletion policy. The current `CaseStore` is process-local.
4. Put per-user/per-tenant rate limiting at API Gateway or the calling app.
5. Set CloudWatch log-group KMS encryption/retention, CloudTrail, alarms, and
   connector receipt monitoring.
6. Run representative, refusal, prompt-injection, and goal-success evals;
   record the baseline before enabling real connectors.

Only after those gates pass should you run `agentcore deploy`, create a named
runtime endpoint, wait for `READY`, and invoke it with a SigV4-signed request.
