from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_is_explicit_about_demo_mode() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["mode"] in {"demo", "live"}


def test_case_has_grounded_evidence_and_approval_gate() -> None:
    response = client.get("/api/case")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "case-042"
    assert len(payload["evidence"]) == 6
    approval_actions = [a for a in payload["actions"] if a["status"] == "needs_approval"]
    assert len(approval_actions) == 1
    assert approval_actions[0]["requires_approval"] is True


def test_run_is_repeatable_and_auditable() -> None:
    client.post("/api/cases/case-042/reset")
    first = client.post("/api/cases/case-042/run").json()
    second = client.post("/api/cases/case-042/run").json()
    assert first["run_count"] == 1
    assert first["mode"] == "demo-strands"
    assert second["run_count"] == 2
    assert len(second["audit"]) == len(first["audit"]) + 1
    assert second["trace"][0]["agent"] == "Evidence Extractor"


def test_approval_requires_the_gate_and_records_receipt() -> None:
    client.post("/api/cases/case-042/reset")
    blocked = client.post(
        "/api/cases/case-042/actions/act-03/approve",
        json={"reviewer": "Demo reviewer", "note": "Try to skip the gate"},
    )
    assert blocked.status_code == 409

    approved = client.post(
        "/api/cases/case-042/actions/act-02/approve",
        json={"reviewer": "Maya's advocate", "note": "Address and notice checked."},
    )
    assert approved.status_code == 200
    action = next(a for a in approved.json()["actions"] if a["id"] == "act-02")
    assert action["status"] == "completed"
    assert "Mock receipt" in action["outcome"]
    assert approved.json()["audit"][-1]["event_type"] == "action.approved"


def test_rejection_becomes_evidence_and_replans_once() -> None:
    client.post("/api/cases/case-042/reset")
    rejected = client.post("/api/cases/case-042/simulate-rejection")
    assert rejected.status_code == 200
    payload = rejected.json()
    assert any(e["id"] == "ev-07" for e in payload["evidence"])
    follow_up = next(a for a in payload["actions"] if a["id"] == "act-06")
    assert follow_up["status"] == "needs_approval"
    assert next(a for a in payload["actions"] if a["id"] == "act-03")["status"] == "blocked"

    repeated = client.post("/api/cases/case-042/simulate-rejection")
    assert repeated.status_code == 200
    assert len([a for a in repeated.json()["actions"] if a["id"] == "act-06"]) == 1


def test_upload_is_quarantined_and_path_traversal_is_rejected() -> None:
    client.post("/api/cases/case-042/reset")
    uploaded = client.post(
        "/api/cases/case-042/evidence",
        files={"file": ("notes.txt", b"The resident has a temporary hotel receipt.", "text/plain")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["evidence"]["status"] == "needs_review"
    assert uploaded.json()["message"].startswith("Evidence quarantined")

    traversal = client.post(
        "/api/cases/case-042/evidence",
        files={"file": ("../../secrets.txt", b"nope", "text/plain")},
    )
    assert traversal.status_code == 415
