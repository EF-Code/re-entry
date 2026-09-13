# Title

RE:ENTRY

## One-line Summary

A human-governed recovery agent that turns crisis paperwork into safe, evidence-linked action.

## Problem

After a flood, eviction, or similar crisis, one person may have to reconcile a county notice, lease, photos, insurer emails, repair estimates, and utility deadlines at the same time. The work is repetitive, but the consequences are not: a wrong amount, an unverified address, or an unreviewed message can delay housing or create a new problem.

RE:ENTRY is designed for residents and the small nonprofit, county, or mutual-aid teams helping them. The product question is not simply “what should an AI say?” It is “what can be safely prepared, what evidence supports it, and where must a person decide before anything leaves the system?”

## Solution

RE:ENTRY turns a recovery case into an inspectable evidence graph and action queue. A Strands Agent proposes a bounded recovery plan from the case snapshot, attaches citations to the source records, flags contradictions instead of guessing, and labels the next actions by risk.

Deterministic policy code remains the authority for side effects. Low-risk work can be prepared, while actions that share personal information or create an official case pause at a human checkpoint. The reviewer sees the exact citations, records a decision note, and approves one action against the case revision they inspected. In the demo, a seeded mock connector returns a receipt after approval. A later connector rejection becomes new evidence, and the planner adds a cited follow-up request while preserving the same approval boundary.

The public demo uses synthetic data and deterministic local connectors. No real resident, agency, insurer, bank, or utility is contacted.

## Why This Matters

The people dealing with a crisis have the least spare attention and the most to lose from an opaque automation. RE:ENTRY makes progress visible without pretending that an agent can replace judgment. It reduces clerical load while keeping evidence, uncertainty, approvals, and outcomes connected in one place.

The same boundary can support a future deployment for disaster-response nonprofits, local government recovery desks, housing advocates, or insurers: the agent can prepare the work, but a trusted human remains responsible for consequential outreach.

## How We Used AI

- The orchestration boundary uses a real `strands.Agent` with structured `AgentPlan` output (`summary`, recommended action IDs, warnings, and confidence).
- The demo uses a deterministic `DemoModel` implementing the same Strands model interface, so judges can run the complete workflow without AWS credentials or network calls.
- `REENTRY_MODE=live` switches to Strands `BedrockModel` with explicit region/model allowlists, bounded turns and token budgets, and safe failure handling.
- The planner receives a minimized case snapshot and a system policy that treats document excerpts, emails, filenames, and quotes as untrusted data—not instructions.
- The planner can only propose known action IDs and cite evidence IDs that exist in the snapshot. It cannot approve, submit, contact a person, move money, or call a real connector.
- Conflicts are surfaced as warnings. Common direct identifiers are redacted from live planner narratives by default, and unreviewed evidence is excluded unless an operator explicitly opts in.

## How We Used Codex

Codex was used as the implementation and verification partner for the project: shaping the product workflow, implementing the FastAPI and React surfaces, integrating the Strands adapter, hardening upload and approval boundaries, writing regression tests and deployment documentation, building the container path, and iterating on the recorded product demo.

The final local verification run for this draft was:

- `~/.venv/bin/pytest -q` — **59 passed**.
- `npm run build` in `frontend/` — **passed** with Vite production output.

## Key Features

- **Evidence graph:** six seeded records across official notices, a lease, a photo, an insurer thread, an estimate, and a utility notice.
- **Conflict-aware planning:** the `$4,680` estimate versus `$5,140` inventory mismatch is held for review rather than inferred away.
- **Evidence-linked action queue:** every proposed action carries source citations, rationale, risk, target, and due time.
- **Human checkpoint:** the emergency housing packet pauses before sharing an address or creating an official case; approval is bound to the inspected case revision.
- **Safe connector simulation:** approval produces a mock receipt; a rejected insurer draft is held and never submitted.
- **Replanning from failure:** the rejection is recorded as evidence and creates a cited “Request signed inventory affidavit” action behind a new approval checkpoint.
- **Quarantined uploads:** bounded, signature-checked uploads are stored as `needs_review` and cannot trigger an external action by themselves.
- **Inspectable trace and audit:** the UI shows the Agent Path, timeline, citations, reviewer note, connector outcome, and safety rationale.

## Architecture

The full diagram and request-flow notes are in [`docs/architecture.md`](docs/architecture.md).

```text
React recovery desk
        │
        ▼
FastAPI HTTP runtime ───────► bounded upload/quarantine boundary
        │
        ├── CaseStore (process-local demo case graph)
        └── Strands coordinator
              ├── Evidence Extractor
              ├── Requirements Planner
              ├── Drafting Verifier
              └── Deterministic Safety Gate
                         ├── low-risk → seeded mock connector
                         └── high-risk → human approval → mock connector
                                      │
                                      └── receipt/rejection → evidence → replanning

Live deployment seam: Strands BedrockModel behind REENTRY_MODE=live;
agentcore/agentcore.json describes a future AWS AgentCore HTTP runtime.
```

The local demo is intentionally offline and process-local. The checked-in AgentCore file is a deployment specification, not proof of an AWS deployment. The documented AWS mapping is FastAPI to AgentCore Runtime, CaseStore to DynamoDB/S3, mock connectors to AgentCore Gateway targets, and the local audit list to managed retention/observability services.

## Testing Instructions

### Fastest local path

1. From the repository root, install the locked development environment:

   ```bash
   ~/.venv/bin/pip install -r requirements-dev.lock
   ~/.venv/bin/pip install -e . --no-deps
   ```

2. Start the API:

   ```bash
   ~/.venv/bin/uvicorn app.main:app --app-dir backend --reload
   ```

3. In a second terminal, start the React UI:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

4. Open `http://127.0.0.1:5173`.

### Judge-friendly demo path

1. Open **Flood recovery / Case 042** and point out the six evidence records, including the `$460` conflict.
2. Select **Review** for **Submit emergency housing packet**. Inspect the three citations and choose **Approve & send**. Confirm the mock receipt and audit entry.
3. Select **Test response** for **Prepare insurer loss package**. The mock connector rejects the draft; confirm the response becomes evidence and **Request signed inventory affidavit** appears behind a new checkpoint.
4. Open **Repair estimate** in the evidence drawer and finish on **Why this is safe** and the **Agent path** strip.

### Regression commands

```bash
~/.venv/bin/ruff check backend tests
~/.venv/bin/pytest -q
cd frontend && npm run build
```

The demo is synthetic and deterministic. It does not require AWS credentials. Live mode is separate and should only be enabled after the deployment gates documented in `docs/production-checklist.md` are complete.

## Public Demo Link

**TODO — optional live demo URL.** No public application endpoint is deployed or verified yet. Local fallback: `http://127.0.0.1:8000` (not a public URL).

## Public Repository Link

[https://github.com/EF-Code/re-entry](https://github.com/EF-Code/re-entry)

The repository is public, includes a README, and is MIT-licensed in [`LICENSE`](LICENSE).

## Demo Video

[RE:ENTRY — Safe Agents for High-Stakes Recovery](https://youtu.be/zrOtw0mPFpc)

The supplied video is approximately one minute and demonstrates the evidence-linked plan, approval checkpoint, mock receipt, connector rejection, replanning, evidence drawer, and Agent Path. **Before final submission, verify that the YouTube video is publicly playable and not private.**

### Video outline

- **0:00–0:10 — Problem:** crisis paperwork is fragmented and consequential.
- **0:10–0:25 — Plan:** six evidence records, a visible amount conflict, and cited actions.
- **0:25–0:40 — Safety gate:** review and approve the housing packet only after inspecting evidence.
- **0:40–0:54 — Failure becomes evidence:** the insurer connector rejects the draft without sending a claim.
- **0:54–1:04 — Replan:** a signed inventory request appears behind a fresh approval checkpoint; finish on the trace and safety promise.

## Screenshot Shot List

No screenshot files were supplied with this draft. Capture 3–5 clean product screenshots before final submission:

1. **Case overview:** Flood recovery / Case 042 with the six evidence cards and one visible conflict.
2. **Human checkpoint:** housing packet approval modal showing the three citations and “Keep paused” option.
3. **Post-approval audit:** completed action, mock receipt, and timeline entry.
4. **Connector rejection:** blocked insurer action, rejection reason, and new affidavit action.
5. **Evidence + Agent Path:** Repair estimate drawer with excerpt/confidence beside the inspectable trace.

## Submission Readiness Notes

### Verified locally

- Real, working project exists in this repository.
- Strands Agents SDK is used in the planner boundary; the demo path is deterministic and offline.
- Public repository URL is known: `https://github.com/EF-Code/re-entry`.
- MIT license and README are present.
- Architecture documentation exists at `docs/architecture.md`.
- Testing instructions and demo path are documented.
- Backend regression suite: **59 passed**.
- Frontend production build: **passed**.
- Demo video URL received: `https://youtu.be/zrOtw0mPFpc`.

### Still required before `$submit-project`

- Verify the YouTube video is public and playable.
- Convert `docs/architecture.md` into an accepted upload format (`pdf`, `ppt`, `pptx`, `png`, `jpg`, or `jpeg`) and attach it to the Devpost submission.
- Provide the exact AWS Builder ID.
- Provide the country of residence for the required form field.
- Confirm the proposed track: **Good Neighbor Agents** (recommended for RE:ENTRY’s community recovery story).
- Confirm the proposed submitter type: **Individual**.
- Capture and upload a project thumbnail/screenshots through the Devpost website if desired; MCP thumbnail upload is separate from the required architecture file.
- Leave the optional live demo URL blank unless a public deployment is actually verified.

## Known Limitations

- The public demo uses synthetic case data and deterministic mock connectors; it contacts no real agencies, residents, insurers, banks, or utilities.
- `CaseStore` is process-local and is not suitable for multi-worker production use.
- Authentication, durable encrypted storage, tenant rate limits, scoped IAM, connector credentials, CloudWatch/X-Ray retention, and a verified public AgentCore endpoint remain deployment work.
- The live Bedrock adapter is implemented but not claimed as deployed or benchmarked in this submission.
- Uploads are bounded and quarantined; binary OCR/visual review is intentionally not performed by the demo.
- The caller-provided reviewer label is explicitly marked unverified in the audit record.

## TODO Official Form Fields

These labels and IDs are copied from the last successful live Devpost requirements response; re-check them in `$submit-project` if Devpost updates the form.

| Field | Devpost ID | Required value / status |
| --- | ---: | --- |
| Submitter Type | 27729 | **Individual** (proposed; confirm) |
| Country of Residence | 27730 | **TODO — provide exact country** |
| Organization name | 27731 | Optional; leave blank |
| Which Track | 27732 | **Good Neighbor Agents** (recommended; confirm) |
| PUBLIC URL to code repo | 27733 | `https://github.com/EF-Code/re-entry` |
| Architecture diagram (REQUIRED) | 27734 | **TODO — upload accepted PDF/PPT/PNG/JPG asset** |
| AWS Builder ID | 27735 | **TODO — provide exact Builder ID** |
| Optional live demo URL | 27736 | Leave blank until a public endpoint is verified |
| testing instructions | 28191 | Use the setup and judge-friendly demo path above |
| Optional Bonus Blog Post URL on builder.aws.com | 27737 | Optional; none provided |

No Codex session ID field appeared in the last successful live requirements response.

