"""FastAPI entrypoint for the RE:ENTRY case workflow."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from pathlib import PurePath

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
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
    RuntimeInvocation,
    UploadReceipt,
)
from .pipeline import approve_action, run_intake, simulate_rejection
from .store import CaseStore

logger = logging.getLogger("re-entry")
app = FastAPI(title="RE:ENTRY", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

store = CaseStore()
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_CONFIGURED_UPLOAD_BYTES = 100 * 1024 * 1024


def _configured_upload_limit() -> int:
    raw_value = os.getenv("REENTRY_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("REENTRY_MAX_UPLOAD_BYTES must be a positive integer") from exc
    if not 1 <= value <= MAX_CONFIGURED_UPLOAD_BYTES:
        raise RuntimeError(
            f"REENTRY_MAX_UPLOAD_BYTES must be between 1 and {MAX_CONFIGURED_UPLOAD_BYTES}"
        )
    return value


def _format_size(value: int) -> str:
    if value % (1024 * 1024) == 0:
        return f"{value // (1024 * 1024)} MB"
    if value % 1024 == 0:
        return f"{value // 1024} KB"
    return f"{value} bytes"


MAX_UPLOAD_BYTES = _configured_upload_limit()
MAX_UPLOAD_LABEL = _format_size(MAX_UPLOAD_BYTES)
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv"}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith(("/api/", "/health", "/ping", "/invocations")):
        response.headers.setdefault("Cache-Control", "no-store")
    if request.url.path == "/" or request.url.path.startswith("/assets/"):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )
    return response


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error method=%s path=%s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def _default_case_id() -> str:
    return os.getenv("REENTRY_CASE_ID", "case-042").strip() or "case-042"


@app.get("/api/health")
@app.get("/health", include_in_schema=False)
@app.get("/ping", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok", "service": "re-entry", "mode": os.getenv("REENTRY_MODE", "demo").lower()}


@app.get("/api/case", response_model=CaseState)
def get_default_case() -> CaseState:
    return _case_or_404(_default_case_id())


def _case_or_404(case_id: str) -> CaseState:
    try:
        return store.get(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@app.post("/invocations", response_model=CaseState, include_in_schema=False)
def invoke_runtime(request: RuntimeInvocation) -> CaseState:
    """Expose a safe plan-only HTTP entrypoint for an AgentCore Runtime adapter."""

    case_id = request.case_id or _default_case_id()
    try:
        return store.apply(case_id, run_intake)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@app.get("/api/cases/{case_id}", response_model=CaseState)
def get_case(case_id: str) -> CaseState:
    return _case_or_404(case_id)


@app.post("/api/cases/{case_id}/run", response_model=CaseState)
def run_case(case_id: str) -> CaseState:
    _case_or_404(case_id)
    try:
        return store.apply(case_id, run_intake)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@app.post("/api/cases/{case_id}/actions/{action_id}/approve", response_model=CaseState)
def approve_case_action(case_id: str, action_id: str, request: ApprovalRequest) -> CaseState:
    _case_or_404(case_id)
    try:
        return store.apply(
            case_id,
            lambda case: approve_action(case, action_id, request.reviewer, request.note),
        )
    except KeyError as exc:
        detail = "Case not found" if exc.args and exc.args[0] == "case_not_found" else "Action not found"
        raise HTTPException(status_code=404, detail=detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Action is not waiting for approval") from exc


@app.post("/api/cases/{case_id}/simulate-rejection", response_model=CaseState)
def reject_case_action(case_id: str) -> CaseState:
    _case_or_404(case_id)
    try:
        return store.apply(case_id, simulate_rejection)
    except KeyError as exc:
        detail = "Case not found" if exc.args and exc.args[0] == "case_not_found" else "Insurer action not found"
        raise HTTPException(status_code=404, detail=detail) from exc


@app.post("/api/cases/{case_id}/reset", response_model=CaseState)
def reset_case(case_id: str) -> CaseState:
    try:
        return store.reset(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@app.post("/api/cases/{case_id}/evidence", response_model=UploadReceipt)
async def upload_evidence(case_id: str, file: UploadFile = File(...)) -> UploadReceipt:  # noqa: B008
    _case_or_404(case_id)
    raw_name = file.filename or ""
    safe_name = PurePath(raw_name).name
    extension = PurePath(safe_name).suffix.lower()
    if (
        not safe_name
        or len(safe_name) > 255
        or safe_name != raw_name
        or "/" in raw_name
        or "\\" in raw_name
        or any(unicodedata.category(character) in {"Cc", "Cf"} for character in raw_name)
        or extension not in ALLOWED_EXTENSIONS
    ):
        raise HTTPException(status_code=415, detail="Use a PDF, text, CSV, PNG, or JPEG file with a safe filename")
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded evidence is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Uploaded evidence exceeds the {MAX_UPLOAD_LABEL} limit")

    full_hash = hashlib.sha256(content).hexdigest()
    content_hash = full_hash[:16]
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
        content_hash=f"sha256:{full_hash}",
    )
    def add_evidence(case: CaseState) -> CaseState:
        if any(item.id == evidence.id for item in case.evidence):
            return case
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
        return case

    try:
        updated = store.apply(case_id, add_evidence)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    stored_evidence = next(item for item in updated.evidence if item.id == evidence.id)
    return UploadReceipt(evidence=stored_evidence, message="Evidence quarantined for review; no action was sent.")


FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
if os.path.isdir(FRONTEND_DIR):
    assets_dir = os.path.join(FRONTEND_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    def frontend_index() -> FileResponse:
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

else:

    @app.get("/", include_in_schema=False)
    def frontend_placeholder() -> JSONResponse:
        return JSONResponse({"service": "re-entry", "message": "Build the frontend with npm run build."})
