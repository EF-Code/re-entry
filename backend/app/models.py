"""Domain models for the RE:ENTRY recovery case graph.

These models are deliberately explicit. The UI can render the agent's work,
the safety gate can make a deterministic decision, and every consequential
transition can be recorded without asking a language model to invent a schema.
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


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
    evidence_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    quote: str = Field(min_length=1, max_length=500)


class Evidence(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=255)
    kind: EvidenceKind
    source: str = Field(min_length=1, max_length=160)
    received_at: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0, le=1)
    status: EvidenceStatus
    excerpt: str = Field(min_length=1, max_length=280)
    tags: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(
        default_factory=list, max_length=20
    )
    content_hash: str | None = Field(default=None, max_length=128)


class Action(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=600)
    connector: str = Field(min_length=1, max_length=160)
    status: ActionStatus
    risk: RiskLevel
    requires_approval: bool
    due: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=600)
    citations: list[Citation] = Field(default_factory=list, max_length=20)
    outcome: str | None = Field(default=None, max_length=600)
    rejection_reason: str | None = Field(default=None, max_length=600)
    created_at: str = Field(min_length=1, max_length=80)
    updated_at: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def high_risk_actions_require_approval(self) -> Action:
        if self.risk == RiskLevel.high and not self.requires_approval:
            raise ValueError("high-risk actions must require human approval")
        return self


class TimelineEvent(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    at: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    detail: str = Field(min_length=1, max_length=600)
    tone: TimelineTone = TimelineTone.neutral
    source: str = Field(default="RE:ENTRY", min_length=1, max_length=160)


class AuditEvent(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    at: str = Field(min_length=1, max_length=80)
    actor: str = Field(min_length=1, max_length=160)
    actor_trust: Literal["system", "unverified_caller", "authenticated_principal"] = "system"
    event_type: str = Field(min_length=1, max_length=80)
    detail: str = Field(min_length=1, max_length=600)
    citations: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(
        default_factory=list, max_length=100
    )
    reversible: bool = True


class TraceStep(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    agent: str = Field(min_length=1, max_length=120)
    status: str = Field(min_length=1, max_length=40)
    detail: str = Field(min_length=1, max_length=600)
    evidence_count: int = Field(default=0, ge=0, le=100)
    action_count: int = Field(default=0, ge=0, le=100)
    duration_ms: int = Field(default=0, ge=0, le=300_000)


class CaseState(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=160)
    county: str = Field(min_length=1, max_length=120)
    opened_at: str = Field(min_length=1, max_length=80)
    phase: str = Field(min_length=1, max_length=80)
    priority: RiskLevel
    summary: str = Field(min_length=1, max_length=600)
    next_deadline: str = Field(min_length=1, max_length=80)
    confidence: float = Field(ge=0, le=1)
    mode: str = Field(default="demo", min_length=1, max_length=40)
    run_count: int = Field(default=0, ge=0, le=100_000)
    evidence: list[Evidence] = Field(default_factory=list, max_length=100)
    actions: list[Action] = Field(default_factory=list, max_length=100)
    timeline: list[TimelineEvent] = Field(default_factory=list, max_length=1_000)
    audit: list[AuditEvent] = Field(default_factory=list, max_length=1_000)
    trace: list[TraceStep] = Field(default_factory=list, max_length=100)


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
            unicodedata.category(character) in {"Cc", "Cf"} and character not in {"\n", "\t", "\r"}
            for character in value
        ):
            raise ValueError("note contains an unsupported control character")
        return " ".join(value.split())


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
