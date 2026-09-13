"""Synthetic case data used by the public demo and repeatable tests."""

from __future__ import annotations

from copy import deepcopy

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


def _citation(evidence_id: str, label: str, quote: str) -> Citation:
    return Citation(evidence_id=evidence_id, label=label, quote=quote)


def _action(
    action_id: str,
    title: str,
    description: str,
    connector: str,
    status: ActionStatus,
    risk: RiskLevel,
    requires_approval: bool,
    due: str,
    target: str,
    rationale: str,
    citations: list[Citation],
) -> Action:
    return Action(
        id=action_id,
        title=title,
        description=description,
        connector=connector,
        status=status,
        risk=risk,
        requires_approval=requires_approval,
        due=due,
        target=target,
        rationale=rationale,
        citations=citations,
        created_at="2026-09-13T08:12:00Z",
        updated_at="2026-09-13T08:12:00Z",
    )


def build_demo_case() -> CaseState:
    """Return a fresh, fully synthetic flood-recovery case."""

    evidence = [
        Evidence(
            id="ev-01",
            title="County flood notice",
            kind=EvidenceKind.official_notice,
            source="Riverton Emergency Management",
            received_at="Sep 08 · 07:14",
            confidence=0.99,
            status=EvidenceStatus.verified,
            excerpt="Zone 4 residents may request emergency housing support after the Sep 7 flood.",
            tags=["official", "deadline", "housing"],
            content_hash="sha256:8b9a1d",
        ),
        Evidence(
            id="ev-02",
            title="Lease + move-in inventory",
            kind=EvidenceKind.agreement,
            source="Uploaded by Maya Okafor",
            received_at="Sep 08 · 07:26",
            confidence=0.94,
            status=EvidenceStatus.verified,
            excerpt="Primary residence: 14 Wren Street, Riverton. Tenancy active through Jun 2027.",
            tags=["identity", "address", "inventory"],
            content_hash="sha256:2a0c44",
        ),
        Evidence(
            id="ev-03",
            title="Site photo · living room",
            kind=EvidenceKind.photo,
            source="Phone upload",
            received_at="Sep 08 · 08:02",
            confidence=0.91,
            status=EvidenceStatus.verified,
            excerpt="Water line visible above skirting board; furniture and appliance damage visible.",
            tags=["damage", "photo", "room-1"],
            content_hash="sha256:9c74bb",
        ),
        Evidence(
            id="ev-04",
            title="Insurer email thread",
            kind=EvidenceKind.email,
            source="Email import",
            received_at="Sep 08 · 08:19",
            confidence=0.84,
            status=EvidenceStatus.needs_review,
            excerpt="Harbor Mutual asks for a signed contents inventory before it will release the claim hold.",
            tags=["insurer", "missing-document", "deadline"],
            content_hash="sha256:1d6e21",
        ),
        Evidence(
            id="ev-05",
            title="Repair estimate",
            kind=EvidenceKind.estimate,
            source="Northbank Repairs",
            received_at="Sep 08 · 09:41",
            confidence=0.76,
            status=EvidenceStatus.conflict,
            excerpt="Estimate says $4,680; the inventory lists a $5,140 replacement total. Reconcile before sending.",
            tags=["amount", "conflict", "insurer"],
            content_hash="sha256:4f92ac",
        ),
        Evidence(
            id="ev-06",
            title="Utility shutoff notice",
            kind=EvidenceKind.official_notice,
            source="Riverton Power",
            received_at="Sep 08 · 10:03",
            confidence=0.97,
            status=EvidenceStatus.verified,
            excerpt="Hardship hold available for 30 days when a county emergency notice is attached.",
            tags=["utility", "verified", "low-risk"],
            content_hash="sha256:0e0c77",
        ),
    ]

    actions = [
        _action(
            "act-01",
            "Request utility hardship hold",
            "Attach the county notice and ask Riverton Power to pause shutoff for 30 days.",
            "Riverton Power mock connector",
            ActionStatus.completed,
            RiskLevel.low,
            False,
            "Completed · Sep 08",
            "Riverton Power · account ending 1842",
            "The county notice explicitly authorizes a hardship hold; no irreversible change is made.",
            [_citation("ev-01", "County notice", "request emergency housing support"), _citation("ev-06", "Utility notice", "Hardship hold available for 30 days")],
        ),
        _action(
            "act-02",
            "Submit emergency housing packet",
            "Send the verified address, county notice, and damage photo to the county housing desk.",
            "Riverton Housing mock connector",
            ActionStatus.needs_approval,
            RiskLevel.high,
            True,
            "Today · 17:00",
            "Riverton County emergency housing desk",
            "The packet is complete, but submission shares a resident address and starts an official case.",
            [_citation("ev-01", "County notice", "may request emergency housing support"), _citation("ev-02", "Lease", "Primary residence: 14 Wren Street"), _citation("ev-03", "Site photo", "Water line visible above skirting board")],
        ),
        _action(
            "act-03",
            "Prepare insurer loss package",
            "Draft the claim packet and hold it until the amount discrepancy is reviewed.",
            "Harbor Mutual mock connector",
            ActionStatus.queued,
            RiskLevel.medium,
            True,
            "Tomorrow · 12:00",
            "Harbor Mutual · claim HM-8842",
            "A $460 discrepancy is visible across the estimate and inventory; the agent will not guess which amount is correct.",
            [_citation("ev-04", "Insurer thread", "signed contents inventory"), _citation("ev-05", "Estimate", "$4,680 vs $5,140")],
        ),
        _action(
            "act-04",
            "Send resident status update",
            "Prepare a plain-language update that explains what is complete and what still needs a decision.",
            "RE:ENTRY message draft",
            ActionStatus.queued,
            RiskLevel.low,
            False,
            "Today · 18:00",
            "Maya Okafor · secure inbox",
            "A draft is reversible and contains only facts already present in the case evidence.",
            [_citation("ev-01", "County notice", "emergency housing support"), _citation("ev-06", "Utility notice", "Hardship hold")],
        ),
        _action(
            "act-05",
            "Schedule debris assessment",
            "Offer three inspection slots after the county marks the street safe.",
            "Riverton Works mock connector",
            ActionStatus.blocked,
            RiskLevel.medium,
            True,
            "Waiting on safety clearance",
            "Riverton Works · Zone 4",
            "The street-safety flag is not yet verified, so RE:ENTRY will not schedule a visit.",
            [_citation("ev-01", "County notice", "Zone 4 residents")],
        ),
    ]

    timeline = [
        TimelineEvent(id="tl-01", at="Sep 08 · 07:14", title="Signal received", detail="County flood notice and resident documents entered the case.", tone=TimelineTone.positive, source="Evidence intake"),
        TimelineEvent(id="tl-02", at="Sep 08 · 08:24", title="Evidence indexed", detail="Six sources were normalised and linked to the address and deadline.", tone=TimelineTone.positive, source="Evidence Extractor"),
        TimelineEvent(id="tl-03", at="Sep 08 · 09:02", title="One contradiction flagged", detail="The insurer estimate and inventory differ by $460; no amount was inferred.", tone=TimelineTone.warning, source="Drafting Verifier"),
        TimelineEvent(id="tl-04", at="Sep 08 · 09:18", title="Recovery plan assembled", detail="Four next steps were drafted across housing, utilities, insurance, and updates.", tone=TimelineTone.active, source="Requirements Planner"),
        TimelineEvent(id="tl-05", at="Now", title="Human checkpoint", detail="One high-stakes action is ready for review before anything is sent.", tone=TimelineTone.active, source="Safety Gate"),
    ]

    audit = [
        AuditEvent(id="au-01", at="Sep 08 · 07:14", actor="Evidence Extractor", event_type="evidence.ingested", detail="Indexed six synthetic documents; source text is treated as untrusted data.", citations=["ev-01", "ev-02", "ev-03", "ev-04", "ev-05", "ev-06"]),
        AuditEvent(id="au-02", at="Sep 08 · 08:24", actor="Requirements Planner", event_type="plan.created", detail="Mapped the county deadline and hardship policy to four possible actions.", citations=["ev-01", "ev-06"]),
        AuditEvent(id="au-03", at="Sep 08 · 09:02", actor="Drafting Verifier", event_type="risk.flagged", detail="Held the insurer packet because two evidence sources disagree on the loss amount.", citations=["ev-04", "ev-05"]),
        AuditEvent(id="au-04", at="Sep 08 · 09:18", actor="Safety Gate", event_type="approval.required", detail="Paused the housing submission because it shares an address with an external agency.", citations=["ev-01", "ev-02", "ev-03"], reversible=False),
    ]

    trace = [
        TraceStep(id="tr-01", agent="Evidence Extractor", status="complete", detail="Normalised 6 sources · 5 verified, 1 needs review", evidence_count=6, duration_ms=412),
        TraceStep(id="tr-02", agent="Requirements Planner", status="complete", detail="Found 4 obligations · 2 deadlines", evidence_count=4, action_count=4, duration_ms=286),
        TraceStep(id="tr-03", agent="Drafting Verifier", status="warning", detail="Held 1 contradiction · $460 amount mismatch", evidence_count=2, action_count=1, duration_ms=337),
        TraceStep(id="tr-04", agent="Safety Gate", status="paused", detail="1 action waiting for human approval", action_count=1, duration_ms=22),
    ]

    return CaseState(
        id="case-042",
        title="Flood recovery / Case 042",
        county="Riverton County",
        opened_at="Sep 08 · 07:14",
        phase="recovery_in_progress",
        priority=RiskLevel.high,
        summary="A flood scattered the resident's paperwork. RE:ENTRY has assembled a grounded recovery plan and paused the one action that shares personal data externally.",
        next_deadline="Today · 17:00",
        confidence=0.89,
        evidence=evidence,
        actions=actions,
        timeline=timeline,
        audit=audit,
        trace=trace,
    )


def clone_demo_case() -> CaseState:
    """Return an independent copy so tests and requests cannot share state."""

    return deepcopy(build_demo_case())

