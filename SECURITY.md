# Security notes

RE:ENTRY is a hackathon prototype. The public demo uses synthetic data and
seeded mock connectors; it is not approved for real claimant documents,
government submissions, insurance claims, or financial actions.

## Current safeguards

- Uploaded evidence is limited to 10 MB, rejects path traversal/control
  characters and overlong names, records a full SHA-256 hash, allows only known
  document/image extensions, and is quarantined as `needs_review`.
- Document excerpts are treated as untrusted data in the Strands system prompt;
  they cannot become tools or instructions.
- External actions are represented by local mock connectors. High-risk actions
  remain behind a deterministic `needs_approval` gate and record reviewer,
  note, citations, and outcome.
- Case transitions are serialized in the in-memory store, preventing concurrent
  requests from approving or recording the same action twice in the demo.
- Provider failures return a safe deterministic fallback; credentials and
  tracebacks are not returned to the browser.
- `/health`, `/ping`, and `/api/*` responses are marked non-cacheable and the
  compiled UI receives clickjacking, MIME-sniffing, referrer, permissions, and
  strict same-origin CSP headers.
- No credentials, `.env` files, uploads, local databases, or build caches are
  tracked by Git.

## Before a real deployment

Use an AgentCore Runtime with AWS IAM or a configured JWT authorizer, scope
Bedrock IAM to the exact model ARN, register outbound credentials through
AgentCore credential providers/Gateway targets, move case data to encrypted
S3/DynamoDB, add per-tenant rate limiting, and retain CloudWatch/CloudTrail
records under an explicit retention policy. Establish representative quality
and red-team evaluations before enabling any connector with real side effects.

If you find a security issue in this prototype, do not include private
documents or credentials in an issue. Contact the repository owner privately
with a minimal reproduction and affected commit SHA.
