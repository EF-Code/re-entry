# Security notes

RE:ENTRY is a hackathon prototype. The public demo uses synthetic data and
seeded mock connectors; it is not approved for real claimant documents,
government submissions, insurance claims, or financial actions.

## Current safeguards

- Uploaded evidence defaults to 10 MB (with a 100 MB configured hard ceiling),
  rejects path traversal/control characters and overlong names, records a full
  SHA-256 hash, allows only known document/image extensions, and is quarantined
  as `needs_review`.
- A bounded ASGI pre-reader rejects oversized or malformed `Content-Length`
  values before JSON/multipart parsing, caps JSON requests at 64 KB, caps an
  upload request at the configured file limit plus 1 MB multipart overhead. It
  streams the body without retaining a replay buffer, caps the number of body
  chunks, and applies a per-chunk read deadline. Each demo case is also capped
  at 100 evidence records and 100 plan passes.
- Document excerpts are treated as untrusted data in the Strands system prompt;
  they cannot become tools or instructions. Live planning refuses to send
  `needs_review` or conflicting evidence unless
  `REENTRY_LIVE_ALLOW_UNREVIEWED_DATA=true` is explicitly set; otherwise the
  provider snapshot contains verified evidence only and a review queue of IDs.
- Live Bedrock configuration is restricted to explicit region and model
  allowlists (`REENTRY_ALLOWED_AWS_REGIONS` and `REENTRY_ALLOWED_MODEL_IDS`),
  which default to the checked-in US geo profile and `us-east-1`.
- External actions are represented by local mock connectors. High-risk actions
  remain behind a deterministic `needs_approval` gate and record reviewer,
  note, citations, and outcome.
- Case transitions are serialized in the in-memory store, preventing concurrent
  requests from approving or recording the same action twice in the demo.
- Provider failures return a safe deterministic fallback; credentials and
  tracebacks are not returned to the browser.
- `/health`, `/ping`, and `/api/*` responses are marked non-cacheable and the
  compiled UI receives clickjacking, MIME-sniffing, referrer, permissions, and
  strict same-origin CSP headers. FastAPI's interactive docs and OpenAPI
  schema are disabled on the unauthenticated demo surface.
- Synthetic reset and connector-rejection routes return `404` when
  `REENTRY_MODE=live`; a live runtime cannot use them to erase or manufacture
  case history.
- The local Compose profile binds its unauthenticated demo port to
  `127.0.0.1` so synthetic case mutations are not exposed to the LAN by
  accident.
- No credentials, `.env` files, uploads, local databases, or build caches are
  tracked by Git.

## Before a real deployment

Use an AgentCore Runtime with AWS IAM or a configured JWT authorizer, scope
Bedrock IAM to the exact model ARN, register outbound credentials through
AgentCore credential providers/Gateway targets, move case data to encrypted
S3/DynamoDB, add per-tenant rate limiting and durable run budgets, and retain
CloudWatch/CloudTrail records under an explicit retention policy. Establish
representative quality and red-team evaluations before enabling any connector
with real side effects. Treat the local reviewer label as unverified until a
trusted authenticated principal is bound to the approval event.

If you find a security issue in this prototype, do not include private
documents or credentials in an issue. Contact the repository owner privately
with a minimal reproduction and affected commit SHA.
