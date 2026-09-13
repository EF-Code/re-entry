"""Case transitions and the deterministic safety boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from .models import (
    Action,
    ActionStatus,
    AuditEvent,
    CaseState,
    Citation,
    Evidence,
    EvidenceKind,
    EvidenceStatus,
    RiskLevel,
    TimelineEvent,
    TimelineTone,
    TraceStep,
)
from .strands_agent import plan_case


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:8]
    return f"{prefix}-{digest}"


def run_intake(case: CaseState) -> CaseState:
    """Run one idempotent plan pass and append a traceable audit event."""

    decision = plan_case(case)
    case.mode = decision.mode
    case.run_count += 1
    case.confidence = decision.confidence
    case.trace = [
        TraceStep(id="tr-01", agent="Evidence Extractor", status="complete", detail="Normalised 6 sources · 5 verified, 1 needs review", evidence_count=len(case.evidence), duration_ms=412),
        TraceStep(id="tr-02", agent="Requirements Planner", status="complete", detail="Found 4 obligations · 2 deadlines", evidence_count=4, action_count=4, duration_ms=286),
        TraceStep(id="tr-03", agent="Drafting Verifier", status="warning", detail="Held 1 contradiction · no amount inferred", evidence_count=2, action_count=1, duration_ms=337),
        TraceStep(id="tr-04", agent="Safety Gate", status="paused", detail="1 action waiting for human approval", action_count=sum(a.status == ActionStatus.needs_approval for a in case.actions), duration_ms=22),
    ]
    timestamp = _now()
    case.timeline.append(
        TimelineEvent(
            id=_id("tl", case.id, str(case.run_count), timestamp),
            at="Just now",
            title="Recovery plan re-checked",
            detail=decision.summary,
            tone=TimelineTone.active,
            source="Strands planner" if decision.mode in {"live", "demo-strands"} else "Deterministic planner",
        )
    )
    case.audit.append(
        AuditEvent(
            id=_id("au", case.id, "run", str(case.run_count)),
            at=timestamp,
            actor="Strands planner" if decision.mode in {"live", "demo-strands"} else "Deterministic planner",
            event_type="plan.rechecked",
            detail=decision.summary,
            citations=[e.id for e in case.evidence],
        )
    )
    return case


def approve_action(case: CaseState, action_id: str, reviewer: str, note: str) -> CaseState:
    """Approve exactly one high-stakes action, then call its mock connector."""

    action = next((item for item in case.actions if item.id == action_id), None)
    if action is None:
        raise KeyError("action_not_found")
    if action.status != ActionStatus.needs_approval or not action.requires_approval:
        raise ValueError("action_not_waiting_for_approval")

    timestamp = _now()
    action.status = ActionStatus.completed
    action.updated_at = timestamp
    action.outcome = f"Mock receipt RE-042-{action.id.upper()} · submitted after human approval"
    case.timeline.append(
        TimelineEvent(
            id=_id("tl", case.id, "approved", action.id, timestamp),
            at="Just now",
            title="Human approval recorded",
            detail=f"{action.title} was sent to {action.connector}.",
            tone=TimelineTone.positive,
            source=reviewer,
        )
    )
    case.audit.append(
        AuditEvent(
            id=_id("au", case.id, "approved", action.id, timestamp),
            at=timestamp,
            actor=reviewer,
            event_type="action.approved",
            detail=note.strip() or "Approved after reviewing the cited evidence.",
            citations=[citation.evidence_id for citation in action.citations],
            reversible=False,
        )
    )
    return case


def simulate_rejection(case: CaseState) -> CaseState:
    """Feed a safe, deterministic connector rejection back into the planner."""

    target = next((item for item in case.actions if item.id == "act-03"), None)
    if target is None:
        raise KeyError("insurer_action_not_found")
    if target.status == ActionStatus.blocked and any(item.id == "act-06" for item in case.actions):
        return case

    timestamp = _now()
    target.status = ActionStatus.blocked
    target.updated_at = timestamp
    target.rejection_reason = "Harbor Mutual mock connector: a signed contents inventory is required."
    target.outcome = "Held safely; no claim was submitted."

    new_evidence = Evidence(
        id="ev-07",
        title="Connector response · missing affidavit",
        kind=EvidenceKind.connector_response,
        source="Harbor Mutual mock connector",
        received_at="Just now",
        confidence=0.98,
        status=EvidenceStatus.needs_review,
        excerpt="The claim can continue after a signed contents inventory is attached.",
        tags=["rejection", "missing-document", "insurer"],
        content_hash="sha256:mock-rejection",
    )
    case.evidence.append(new_evidence)
    case.actions.append(
        Action(
            id="act-06",
            title="Request signed inventory affidavit",
            description="Prepare a plain-language request for the missing signed inventory; do not submit the claim yet.",
            connector="Harbor Mutual mock connector",
            status=ActionStatus.needs_approval,
            risk=RiskLevel.medium,
            requires_approval=True,
            due="Tomorrow · 12:00",
            target="Maya Okafor · secure inbox",
            rationale="The connector named the missing document, but contacting the resident is still an external action.",
            citations=[
                Citation(evidence_id="ev-04", label="Insurer thread", quote="signed contents inventory"),
                Citation(evidence_id="ev-07", label="Connector response", quote="after a signed contents inventory is attached"),
            ],
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    case.trace.extend(
        [
            TraceStep(id="tr-05", agent="Harbor Mutual connector", status="returned", detail="Rejected safely · missing signed inventory", evidence_count=1, duration_ms=184),
            TraceStep(id="tr-06", agent="Replanner", status="complete", detail="Added 1 cited follow-up · still paused for approval", evidence_count=2, action_count=1, duration_ms=201),
        ]
    )
    case.timeline.extend(
        [
            TimelineEvent(id=_id("tl", case.id, "rejected", timestamp), at="Just now", title="Connector asked for one missing document", detail="Harbor Mutual rejected the draft without changing the claim; the response is now evidence.", tone=TimelineTone.warning, source="Harbor Mutual mock connector"),
            TimelineEvent(id=_id("tl", case.id, "replanned", timestamp), at="Just now", title="Recovery plan adapted", detail="RE:ENTRY added a signed inventory request and kept it behind the human checkpoint.", tone=TimelineTone.active, source="Replanner"),
        ]
    )
    case.audit.extend(
        [
            AuditEvent(id=_id("au", case.id, "rejected", timestamp), at=timestamp, actor="Harbor Mutual mock connector", event_type="connector.rejected", detail="Draft held; connector requested a signed contents inventory.", citations=["ev-04", "ev-07"]),
            AuditEvent(id=_id("au", case.id, "replanned", timestamp), at=timestamp, actor="Replanner", event_type="plan.adapted", detail="Added a cited follow-up and preserved the approval gate.", citations=["ev-04", "ev-07"]),
        ]
    )
    return case
