"""FastAPI entrypoint for the RE:ENTRY case workflow."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
import unicodedata
from pathlib import PurePath
from threading import Lock

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

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
from .pipeline import (
    MAX_CASE_PLAN_RUNS,
    approve_action,
    configured_plan_run_limit,
    run_intake,
    simulate_rejection,
)
from .store import CaseStore

logger = logging.getLogger("re-entry")
# The browser uses the compiled UI rather than FastAPI's interactive schema.
# Keep the unauthenticated demo surface small; production deployments should
# expose API documentation separately behind their normal identity boundary.
app = FastAPI(
    title="RE:ENTRY",
    version="0.2.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

store = CaseStore()
DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_CONFIGURED_UPLOAD_BYTES = 100 * 1024 * 1024
DEFAULT_REQUEST_READ_TIMEOUT_SECONDS = 30
MAX_CONFIGURED_REQUEST_READ_TIMEOUT_SECONDS = 300
DEFAULT_REQUEST_MAX_DURATION_SECONDS = 300
MAX_CONFIGURED_REQUEST_MAX_DURATION_SECONDS = 3_600
DEFAULT_MAX_IN_FLIGHT_REQUESTS = 32
MAX_CONFIGURED_MAX_IN_FLIGHT_REQUESTS = 256
DEFAULT_MAX_IN_FLIGHT_BODY_BYTES = 256 * 1024 * 1024
MAX_CONFIGURED_MAX_IN_FLIGHT_BODY_BYTES = 1 * 1024 * 1024 * 1024


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


def _configured_request_read_timeout() -> float:
    raw_value = os.getenv(
        "REENTRY_REQUEST_READ_TIMEOUT_SECONDS",
        str(DEFAULT_REQUEST_READ_TIMEOUT_SECONDS),
    )
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            "REENTRY_REQUEST_READ_TIMEOUT_SECONDS must be a positive number"
        ) from exc
    if not 1 <= value <= MAX_CONFIGURED_REQUEST_READ_TIMEOUT_SECONDS:
        raise RuntimeError(
            "REENTRY_REQUEST_READ_TIMEOUT_SECONDS must be between 1 and "
            f"{MAX_CONFIGURED_REQUEST_READ_TIMEOUT_SECONDS}"
        )
    return value


def _configured_request_max_duration() -> float:
    raw_value = os.getenv(
        "REENTRY_REQUEST_MAX_DURATION_SECONDS",
        str(DEFAULT_REQUEST_MAX_DURATION_SECONDS),
    )
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise RuntimeError(
            "REENTRY_REQUEST_MAX_DURATION_SECONDS must be a positive number"
        ) from exc
    if not 1 <= value <= MAX_CONFIGURED_REQUEST_MAX_DURATION_SECONDS:
        raise RuntimeError(
            "REENTRY_REQUEST_MAX_DURATION_SECONDS must be between 1 and "
            f"{MAX_CONFIGURED_REQUEST_MAX_DURATION_SECONDS}"
        )
    if value < REQUEST_READ_TIMEOUT_SECONDS:
        raise RuntimeError(
            "REENTRY_REQUEST_MAX_DURATION_SECONDS must be at least "
            "REENTRY_REQUEST_READ_TIMEOUT_SECONDS"
        )
    return value


def _configured_positive_limit(name: str, default: int, maximum: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if not 1 <= value <= maximum:
        raise RuntimeError(f"{name} must be between 1 and {maximum}")
    return value


def _format_size(value: int) -> str:
    if value % (1024 * 1024) == 0:
        return f"{value // (1024 * 1024)} MB"
    if value % 1024 == 0:
        return f"{value // 1024} KB"
    return f"{value} bytes"


MAX_UPLOAD_BYTES = _configured_upload_limit()
MAX_UPLOAD_LABEL = _format_size(MAX_UPLOAD_BYTES)
REQUEST_READ_TIMEOUT_SECONDS = _configured_request_read_timeout()
REQUEST_MAX_DURATION_SECONDS = _configured_request_max_duration()
MAX_IN_FLIGHT_REQUESTS = _configured_positive_limit(
    "REENTRY_MAX_IN_FLIGHT_REQUESTS",
    DEFAULT_MAX_IN_FLIGHT_REQUESTS,
    MAX_CONFIGURED_MAX_IN_FLIGHT_REQUESTS,
)
MAX_IN_FLIGHT_BODY_BYTES = _configured_positive_limit(
    "REENTRY_MAX_IN_FLIGHT_BODY_BYTES",
    DEFAULT_MAX_IN_FLIGHT_BODY_BYTES,
    MAX_CONFIGURED_MAX_IN_FLIGHT_BODY_BYTES,
)
MAX_JSON_BODY_BYTES = 64 * 1024
MAX_MULTIPART_OVERHEAD_BYTES = 1024 * 1024
MAX_CASE_EVIDENCE = 100
# An upload is hashed in full for deduplication, but only a small prefix is
# needed for the bounded human-review excerpt. Avoid decoding/regex-scanning a
# 100 MB text upload when the UI will retain at most 280 characters.
MAX_TEXT_EXCERPT_SOURCE_BYTES = 64 * 1024
UPLOAD_READ_CHUNK_BYTES = 64 * 1024
MAX_REQUEST_CHUNKS = 4096
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg"}
TEXT_EXTENSIONS = {".txt", ".md", ".csv"}


class RequestBodyTooLargeError(Exception):
    """Raised by the streaming receiver before a parser can overrun its cap."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class RequestBodyReadTimeoutError(Exception):
    """Raised when a client stalls between bounded body chunks."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


_in_flight_lock = Lock()
_in_flight_requests = 0
_in_flight_body_bytes = 0


def _try_reserve_request(body_bytes: int) -> bool:
    global _in_flight_body_bytes, _in_flight_requests
    with _in_flight_lock:
        if _in_flight_requests >= MAX_IN_FLIGHT_REQUESTS:
            return False
        if _in_flight_body_bytes + body_bytes > MAX_IN_FLIGHT_BODY_BYTES:
            return False
        _in_flight_requests += 1
        _in_flight_body_bytes += body_bytes
        return True


def _release_request(body_bytes: int) -> None:
    global _in_flight_body_bytes, _in_flight_requests
    with _in_flight_lock:
        _in_flight_requests = max(0, _in_flight_requests - 1)
        _in_flight_body_bytes = max(0, _in_flight_body_bytes - body_bytes)


def _request_limit_for_scope(scope: Scope) -> tuple[int, str] | None:
    """Return a hard byte limit for request bodies that the app parses."""

    if scope.get("method") not in {"POST", "PUT", "PATCH"}:
        return None
    path = scope.get("path", "")
    if path.startswith("/api/cases/") and path.endswith("/evidence"):
        return (
            MAX_UPLOAD_BYTES + MAX_MULTIPART_OVERHEAD_BYTES,
            f"Uploaded request exceeds the {MAX_UPLOAD_LABEL} limit",
        )
    if path == "/invocations" or path.startswith("/api/"):
        return MAX_JSON_BODY_BYTES, "Request body exceeds the 64 KB limit"
    return None


def _content_length_value(headers: Headers) -> tuple[int | None, str | None]:
    """Parse one strict, non-negative Content-Length value."""

    values = headers.getlist("content-length")
    if not values:
        return None, None
    if len(values) != 1:
        return None, "Invalid Content-Length header"
    value = values[0].strip()
    if not value or any(character not in "0123456789" for character in value):
        return None, "Invalid Content-Length header"
    try:
        return int(value), None
    except ValueError:
        return None, "Invalid Content-Length header"


def _set_security_headers(response: JSONResponse, path: str) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if path.startswith(("/api/", "/health", "/ping", "/invocations")):
        response.headers.setdefault("Cache-Control", "no-store")
    if path == "/" or path.startswith("/assets/"):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        )


async def _send_limit_error(scope: Scope, send: Send, status_code: int, detail: str) -> None:
    """Send a bounded-request error with the app's normal response headers."""

    path = scope.get("path", "")
    response = JSONResponse(status_code=status_code, content={"detail": detail})
    _set_security_headers(response, path)
    origin = Headers(scope=scope).get("origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    await response(scope, _empty_receive, send)


async def _empty_receive() -> dict[str, object]:
    return {"type": "http.disconnect"}


async def _consume_upload(file: UploadFile, max_bytes: int) -> tuple[int, str, bytes]:
    """Hash an upload incrementally and retain only the bounded text prefix.

    Starlette's multipart parser may spool the part to a temporary file, but
    reading the entire part into one ``bytes`` object here would still let a
    valid, near-limit upload consume a large amount of application memory.
    Reading one bounded chunk at a time keeps the route's working set stable
    while the request middleware enforces the complete multipart envelope.
    """

    digest = hashlib.sha256()
    excerpt = bytearray()
    total = 0
    while True:
        # Read one extra byte once the cap is reached so an over-limit upload
        # is rejected without retaining or hashing an unbounded body.
        read_size = min(UPLOAD_READ_CHUNK_BYTES, max_bytes - total + 1)
        chunk = await file.read(read_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Uploaded evidence exceeds the {MAX_UPLOAD_LABEL} limit",
            )
        digest.update(chunk)
        remaining_excerpt = MAX_TEXT_EXCERPT_SOURCE_BYTES - len(excerpt)
        if remaining_excerpt > 0:
            excerpt.extend(chunk[:remaining_excerpt])
    return total, digest.hexdigest(), bytes(excerpt)


def _safe_text_excerpt(source: bytes) -> str:
    """Normalize an upload prefix before it is shown or sent to a planner."""

    decoded = source.decode("utf-8", errors="replace")
    sanitized = "".join(
        " " if unicodedata.category(character) in {"Cc", "Cf", "Cs"} else character
        for character in decoded
    )
    return re.sub(r"\s+", " ", sanitized).strip()[:280]


class RequestBodyLimitMiddleware:
    """Bound request bytes before Starlette parses JSON or multipart bodies."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        limit = _request_limit_for_scope(scope)
        if scope.get("type") != "http" or limit is None:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        is_upload = scope.get("path", "").startswith("/api/cases/") and scope.get("path", "").endswith("/evidence")
        content_length, content_length_error = _content_length_value(headers)
        if content_length_error:
            await _send_limit_error(scope, send, 400, content_length_error)
            return
        if is_upload and content_length is None:
            await _send_limit_error(scope, send, 411, "Content-Length is required for evidence uploads")
            return
        if content_length is not None and content_length > limit[0]:
            await _send_limit_error(scope, send, 413, limit[1])
            return

        reserved_body_bytes = content_length if content_length is not None else limit[0]
        if not _try_reserve_request(reserved_body_bytes):
            await _send_limit_error(scope, send, 429, "Too many requests in flight")
            return

        received_bytes = 0
        received_chunks = 0
        deadline = time.monotonic() + REQUEST_MAX_DURATION_SECONDS

        async def limited_receive() -> dict[str, object]:
            nonlocal received_bytes, received_chunks
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RequestBodyReadTimeoutError("Request body exceeded the maximum duration")
            try:
                message = await asyncio.wait_for(
                    receive(), timeout=min(REQUEST_READ_TIMEOUT_SECONDS, remaining)
                )
            except TimeoutError as exc:
                raise RequestBodyReadTimeoutError("Request body read timed out") from exc
            if time.monotonic() > deadline:
                raise RequestBodyReadTimeoutError("Request body exceeded the maximum duration")
            if message["type"] == "http.request":
                received_chunks += 1
                if received_chunks > MAX_REQUEST_CHUNKS:
                    raise RequestBodyTooLargeError("Request contains too many body chunks")
                received_bytes += len(message.get("body", b""))
                if received_bytes > limit[0]:
                    raise RequestBodyTooLargeError(limit[1])
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestBodyTooLargeError as exc:
            await _send_limit_error(scope, send, 413, exc.detail)
        except RequestBodyReadTimeoutError as exc:
            await _send_limit_error(scope, send, 408, exc.detail)
        finally:
            _release_request(reserved_body_bytes)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    _set_security_headers(response, request.url.path)
    return response


app.add_middleware(RequestBodyLimitMiddleware)


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled application error method=%s path=%s error_type=%s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(RequestBodyTooLargeError)
async def handle_body_limit_error(request: Request, exc: RequestBodyTooLargeError) -> JSONResponse:
    response = JSONResponse(status_code=413, content={"detail": exc.detail})
    _set_security_headers(response, request.url.path)
    return response


@app.exception_handler(RequestBodyReadTimeoutError)
async def handle_body_timeout_error(request: Request, exc: RequestBodyReadTimeoutError) -> JSONResponse:
    response = JSONResponse(status_code=408, content={"detail": exc.detail})
    _set_security_headers(response, request.url.path)
    return response


def _default_case_id() -> str:
    return os.getenv("REENTRY_CASE_ID", "case-042").strip() or "case-042"


def _runtime_mode() -> str:
    mode = os.getenv("REENTRY_MODE", "demo").strip().lower() or "demo"
    return mode if mode in {"demo", "live"} else "invalid"


def _ephemeral_store_is_explicitly_allowed() -> bool:
    """Allow the in-memory store in live mode only for local synthetic tests."""

    return os.getenv("REENTRY_ALLOW_EPHEMERAL_STORE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _require_storage_ready() -> None:
    """Fail closed until live mode has a durable storage implementation."""

    mode = _runtime_mode()
    if mode == "invalid":
        raise HTTPException(status_code=503, detail="Runtime is not ready: unsupported REENTRY_MODE")
    if mode == "live" and not _ephemeral_store_is_explicitly_allowed():
        raise HTTPException(
            status_code=503,
            detail="Live runtime is not ready: durable case storage is required",
        )


def _plan_limit_for_error() -> int:
    """Use the effective budget in a response without exposing bad config."""

    try:
        return configured_plan_run_limit()
    except RuntimeError:
        return MAX_CASE_PLAN_RUNS


def _require_demo_mode() -> None:
    """Keep synthetic reset/rejection controls out of a live runtime."""

    if _runtime_mode() != "demo":
        raise HTTPException(status_code=404, detail="Demo-only route unavailable")


@app.get("/api/health")
@app.get("/health", include_in_schema=False)
@app.get("/ping", include_in_schema=False)
def health() -> JSONResponse:
    mode = _runtime_mode()
    if mode == "invalid":
        response = JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "re-entry",
                "mode": mode,
                "detail": "Unsupported REENTRY_MODE; use demo or live",
            },
        )
        _set_security_headers(response, "/health")
        return response
    if mode == "live" and not _ephemeral_store_is_explicitly_allowed():
        response = JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "re-entry",
                "mode": mode,
                "detail": "Durable case storage is required before live mode can serve traffic",
            },
        )
        _set_security_headers(response, "/health")
        return response
    response = JSONResponse(
        content={
            "status": "ok",
            "service": "re-entry",
            "mode": mode,
        }
    )
    _set_security_headers(response, "/health")
    return response


@app.get("/api/case", response_model=CaseState)
def get_default_case() -> CaseState:
    return _case_or_404(_default_case_id())


def _case_or_404(case_id: str) -> CaseState:
    _require_storage_ready()
    try:
        return store.get(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@app.post("/invocations", response_model=CaseState, include_in_schema=False)
def invoke_runtime(request: RuntimeInvocation) -> CaseState:
    """Expose a safe plan-only HTTP entrypoint for an AgentCore Runtime adapter."""

    _require_storage_ready()
    case_id = request.case_id or _default_case_id()
    try:
        return store.apply(case_id, run_intake)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except ValueError as exc:
        if exc.args and exc.args[0] == "plan_run_limit_reached":
            raise HTTPException(status_code=429, detail=f"Case plan run limit reached ({_plan_limit_for_error()})") from exc
        if exc.args and exc.args[0] == "case_revision_limit_reached":
            raise HTTPException(status_code=409, detail="Case revision limit reached") from exc
        raise


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
    except ValueError as exc:
        if exc.args and exc.args[0] == "plan_run_limit_reached":
            raise HTTPException(status_code=429, detail=f"Case plan run limit reached ({_plan_limit_for_error()})") from exc
        if exc.args and exc.args[0] == "case_revision_limit_reached":
            raise HTTPException(status_code=409, detail="Case revision limit reached") from exc
        raise


@app.post("/api/cases/{case_id}/actions/{action_id}/approve", response_model=CaseState)
def approve_case_action(case_id: str, action_id: str, request: ApprovalRequest) -> CaseState:
    _case_or_404(case_id)
    try:
        return store.apply(
            case_id,
            lambda case: approve_action(
                case,
                action_id,
                request.reviewer,
                request.note,
                request.expected_revision,
            ),
        )
    except KeyError as exc:
        detail = "Case not found" if exc.args and exc.args[0] == "case_not_found" else "Action not found"
        raise HTTPException(status_code=404, detail=detail) from exc
    except ValueError as exc:
        if exc.args and exc.args[0] == "approval_revision_required":
            raise HTTPException(status_code=428, detail="Approval must include the current case revision") from exc
        if exc.args and exc.args[0] == "stale_case_revision":
            raise HTTPException(status_code=409, detail="Case changed; reload before approving") from exc
        if exc.args and exc.args[0] == "case_revision_limit_reached":
            raise HTTPException(status_code=409, detail="Case revision limit reached") from exc
        raise HTTPException(status_code=409, detail="Action is not waiting for approval") from exc


@app.post("/api/cases/{case_id}/simulate-rejection", response_model=CaseState)
def reject_case_action(case_id: str) -> CaseState:
    _require_demo_mode()
    _case_or_404(case_id)
    try:
        return store.apply(
            case_id,
            lambda case: simulate_rejection(case, max_evidence=MAX_CASE_EVIDENCE),
        )
    except KeyError as exc:
        detail = "Case not found" if exc.args and exc.args[0] == "case_not_found" else "Insurer action not found"
        raise HTTPException(status_code=404, detail=detail) from exc
    except ValueError as exc:
        if exc.args and exc.args[0] == "evidence_limit_reached":
            raise HTTPException(status_code=409, detail=f"Case evidence limit reached ({MAX_CASE_EVIDENCE})") from exc
        if exc.args and exc.args[0] == "case_revision_limit_reached":
            raise HTTPException(status_code=409, detail="Case revision limit reached") from exc
        raise


@app.post("/api/cases/{case_id}/reset", response_model=CaseState)
def reset_case(case_id: str) -> CaseState:
    _require_demo_mode()
    try:
        return store.reset(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except ValueError as exc:
        if exc.args and exc.args[0] == "case_revision_limit_reached":
            raise HTTPException(status_code=409, detail="Case revision limit reached") from exc
        raise


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
        or any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in raw_name)
        or extension not in ALLOWED_EXTENSIONS
    ):
        raise HTTPException(status_code=415, detail="Use a PDF, text, CSV, PNG, or JPEG file with a safe filename")
    try:
        total_size, full_hash, excerpt_source = await _consume_upload(file, MAX_UPLOAD_BYTES)
    finally:
        await file.close()
    if total_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded evidence is empty")

    if extension in TEXT_EXTENSIONS:
        excerpt = _safe_text_excerpt(excerpt_source)
    else:
        excerpt = "Binary evidence received; visual/OCR review is required before use."
    evidence = Evidence(
        id=f"upload-{full_hash}",
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
        if len(case.evidence) >= MAX_CASE_EVIDENCE:
            raise ValueError("evidence_limit_reached")
        case.evidence.append(evidence)
        case.audit.append(
            AuditEvent(
                id=f"au-upload-{full_hash}",
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
    except ValueError as exc:
        if exc.args and exc.args[0] == "evidence_limit_reached":
            raise HTTPException(status_code=409, detail=f"Case evidence limit reached ({MAX_CASE_EVIDENCE})") from exc
        if exc.args and exc.args[0] == "case_revision_limit_reached":
            raise HTTPException(status_code=409, detail="Case revision limit reached") from exc
        raise
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

    @app.get("/favicon.svg", include_in_schema=False)
    def frontend_favicon() -> FileResponse:
        return FileResponse(os.path.join(FRONTEND_DIR, "favicon.svg"), media_type="image/svg+xml")

else:

    @app.get("/", include_in_schema=False)
    def frontend_placeholder() -> JSONResponse:
        return JSONResponse({"service": "re-entry", "message": "Build the frontend with npm run build."})
