"""Domain models for the RE:ENTRY recovery case graph.

These models are deliberately explicit. The UI can render the agent's work,
the safety gate can make a deterministic decision, and every consequential
transition can be recorded without asking a language model to invent a schema.
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EvidenceKind(StrEnum):
    official_notice = "official_notice"
    agreement = "agreement"
    photo = "photo"
    email = "email"
    estimate = "estimate"
    connector_response = "connector_response"
    upload = "upload"


class EvidenceStatus(StrEnum):
    verified = "verified"
    needs_review = "needs_review"
    conflict = "conflict"


class ActionStatus(StrEnum):
    queued = "queued"
    needs_approval = "needs_approval"
    in_progress = "in_progress"
    completed = "completed"
    blocked = "blocked"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class TimelineTone(StrEnum):
    neutral = "neutral"
    positive = "positive"
    warning = "warning"
    active = "active"


class Citation(BaseModel):
    evidence_id: str
    label: str
    quote: str


class Evidence(BaseModel):
    id: str
    title: str
    kind: EvidenceKind
    source: str
    received_at: str
    confidence: float = Field(ge=0, le=1)
    status: EvidenceStatus
    excerpt: str
    tags: list[str] = Field(default_factory=list)
    content_hash: str | None = None


class Action(BaseModel):
    id: str
    title: str
    description: str
    connector: str
    status: ActionStatus
    risk: RiskLevel
    requires_approval: bool
    due: str
    target: str
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    outcome: str | None = None
    rejection_reason: str | None = None
    created_at: str
    updated_at: str


class TimelineEvent(BaseModel):
    id: str
    at: str
    title: str
    detail: str
    tone: TimelineTone = TimelineTone.neutral
    source: str = "RE:ENTRY"


class AuditEvent(BaseModel):
    id: str
    at: str
    actor: str
    actor_trust: Literal["system", "unverified_caller", "authenticated_principal"] = "system"
    event_type: str
    detail: str
    citations: list[str] = Field(default_factory=list)
    reversible: bool = True


class TraceStep(BaseModel):
    id: str
    agent: str
    status: str
    detail: str
    evidence_count: int = 0
    action_count: int = 0
    duration_ms: int = 0


class CaseState(BaseModel):
    id: str
    title: str
    county: str
    opened_at: str
    phase: str
    priority: RiskLevel
    summary: str
    next_deadline: str
    confidence: float = Field(ge=0, le=1)
    mode: str = "demo"
    run_count: int = 0
    evidence: list[Evidence] = Field(default_factory=list)
    actions: list[Action] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    audit: list[AuditEvent] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    reviewer: str = Field(default="Demo reviewer", min_length=2, max_length=80)
    note: str = Field(default="Approved after reviewing the cited evidence.", max_length=500)

    @field_validator("reviewer")
    @classmethod
    def reviewer_must_contain_text(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2 or any(unicodedata.category(character) in {"Cc", "Cf"} for character in cleaned):
            raise ValueError("reviewer must contain at least two non-whitespace characters")
        return cleaned

    @field_validator("note")
    @classmethod
    def note_must_not_contain_control_data(cls, value: str) -> str:
        if any(
            unicodedata.category(character) in {"Cc", "Cf"} and character not in {"\n", "\t"}
            for character in value
        ):
            raise ValueError("note contains an unsupported control character")
        return value.strip()


class RuntimeInvocation(BaseModel):
    """Small, bounded payload for AgentCore's HTTP invocation contract."""

    case_id: str | None = Field(default=None, max_length=64)
    operation: Literal["plan"] = "plan"

    @field_validator("case_id")
    @classmethod
    def case_id_must_be_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or any(unicodedata.category(character) in {"Cc", "Cf"} for character in cleaned):
            raise ValueError("case_id must contain printable characters")
        return cleaned


class UploadReceipt(BaseModel):
    evidence: Evidence
    message: str
