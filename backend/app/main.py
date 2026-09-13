"""FastAPI entrypoint for the RE:ENTRY case workflow."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import PurePath

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    ApprovalRequest,
    AuditEvent,
    CaseState,
    Evidence,
    EvidenceKind,
    EvidenceStatus,
    UploadReceipt,
)
from .pipeline import approve_action, run_intake, simulate_rejection
from .store import CaseStore

app = FastAPI(title="RE:ENTRY", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

store = CaseStore()
MAX_UPLOAD_BYTES = int(os.getenv("REENTRY_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "re-entry", "mode": os.getenv("REENTRY_MODE", "demo")}


@app.get("/api/case", response_model=CaseState)
def get_default_case() -> CaseState:
    return store.get(os.getenv("REENTRY_CASE_ID", "case-042"))


def _case_or_404(case_id: str) -> CaseState:
    try:
        return store.get(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@app.get("/api/cases/{case_id}", response_model=CaseState)
def get_case(case_id: str) -> CaseState:
    return _case_or_404(case_id)


@app.post("/api/cases/{case_id}/run", response_model=CaseState)
def run_case(case_id: str) -> CaseState:
    case = _case_or_404(case_id)
    return store.put(run_intake(case))


@app.post("/api/cases/{case_id}/actions/{action_id}/approve", response_model=CaseState)
def approve_case_action(case_id: str, action_id: str, request: ApprovalRequest) -> CaseState:
    case = _case_or_404(case_id)
    try:
        updated = approve_action(case, action_id, request.reviewer, request.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Action not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Action is not waiting for approval") from exc
    return store.put(updated)


@app.post("/api/cases/{case_id}/simulate-rejection", response_model=CaseState)
def reject_case_action(case_id: str) -> CaseState:
    case = _case_or_404(case_id)
    try:
        updated = simulate_rejection(case)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Insurer action not found") from exc
    return store.put(updated)


@app.post("/api/cases/{case_id}/reset", response_model=CaseState)
def reset_case(case_id: str) -> CaseState:
    try:
        return store.reset(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@app.post("/api/cases/{case_id}/evidence", response_model=UploadReceipt)
async def upload_evidence(case_id: str, file: UploadFile = File(...)) -> UploadReceipt:  # noqa: B008
    case = _case_or_404(case_id)
    raw_name = file.filename or ""
    safe_name = PurePath(raw_name).name
    extension = PurePath(safe_name).suffix.lower()
    if not safe_name or safe_name != raw_name or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Use a PDF, text, CSV, PNG, or JPEG file with a safe filename")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded evidence is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded evidence exceeds the 10 MB limit")

    content_hash = hashlib.sha256(content).hexdigest()[:12]
    if extension in TEXT_EXTENSIONS:
        excerpt = re.sub(r"\s+", " ", content.decode("utf-8", errors="replace")).strip()[:280]
    else:
        excerpt = "Binary evidence received; visual/OCR review is required before use."
    evidence = Evidence(
        id=f"upload-{content_hash}",
        title=safe_name,
        kind=EvidenceKind.upload,
        source="Local demo upload",
        received_at="Just now",
        confidence=0.55 if extension not in TEXT_EXTENSIONS else 0.68,
        status=EvidenceStatus.needs_review,
        excerpt=excerpt or "Text evidence contained no readable characters.",
        tags=["uploaded", "needs-review"],
        content_hash=f"sha256:{content_hash}",
    )
    if not any(item.id == evidence.id for item in case.evidence):
        case.evidence.append(evidence)
        case.audit.append(
            AuditEvent(
                id=f"au-upload-{content_hash}",
                at="Just now",
                actor="Evidence intake",
                event_type="evidence.uploaded",
                detail="Uploaded evidence was quarantined for review; it cannot trigger an external action by itself.",
                citations=[evidence.id],
                reversible=True,
            )
        )
        store.put(case)
    return UploadReceipt(evidence=evidence, message="Evidence quarantined for review; no action was sent.")


FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

else:

    @app.get("/", include_in_schema=False)
    def frontend_placeholder() -> JSONResponse:
        return JSONResponse({"service": "re-entry", "message": "Build the frontend with npm run build."})
