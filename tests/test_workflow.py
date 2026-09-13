import pytest
from app import main as main_module
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_is_explicit_about_demo_mode() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["mode"] in {"demo", "live"}


def test_runtime_health_aliases_and_plan_invocation_contract() -> None:
    for path in ("/health", "/ping"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.headers["cache-control"] == "no-store"

    client.post("/api/cases/case-042/reset")
    invocation = client.post("/invocations", json={"case_id": "case-042"})
    assert invocation.status_code == 200
    assert invocation.json()["run_count"] == 1

    missing = client.post("/invocations", json={"case_id": "missing"})
    assert missing.status_code == 404
    unsupported = client.post("/invocations", json={"operation": "send_money"})
    assert unsupported.status_code == 422


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


def test_trace_counts_follow_case_mutations() -> None:
    client.post("/api/cases/case-042/reset")
    uploaded = client.post(
        "/api/cases/case-042/evidence",
        files={"file": ("receipt.txt", b"A temporary hotel receipt.", "text/plain")},
    )
    assert uploaded.status_code == 200
    after_upload = client.post("/api/cases/case-042/run").json()
    assert after_upload["trace"][0]["detail"].startswith("Normalised 7 sources")
    assert after_upload["trace"][0]["evidence_count"] == 7

    rejected = client.post("/api/cases/case-042/simulate-rejection")
    assert rejected.status_code == 200
    after_rejection = client.post("/api/cases/case-042/run").json()
    assert after_rejection["trace"][0]["detail"].startswith("Normalised 8 sources")
    assert after_rejection["trace"][3]["action_count"] == 2


def test_strands_failures_keep_the_demo_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    client.post("/api/cases/case-042/reset")

    def fail_demo(_: object):
        raise RuntimeError("simulated SDK incompatibility")

    import app.strands_agent as strands_module

    monkeypatch.setattr(strands_module, "invoke_demo_strands", fail_demo)
    fallback = client.post("/api/cases/case-042/run")
    assert fallback.status_code == 200
    assert fallback.json()["mode"] == "demo"
    assert "6 case sources" in fallback.json()["audit"][-1]["detail"]


def test_default_case_configuration_is_a_safe_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REENTRY_CASE_ID", "does-not-exist")
    response = client.get("/api/case")
    assert response.status_code == 404
    monkeypatch.delenv("REENTRY_CASE_ID")


def test_unexpected_errors_return_a_safe_message(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_get(_: str):
        raise RuntimeError("internal details must not escape")

    monkeypatch.setattr(main_module.store, "get", fail_get)
    isolated_client = TestClient(app, raise_server_exceptions=False)
    response = isolated_client.get("/api/case")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


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

    whitespace_reviewer = client.post(
        "/api/cases/case-042/actions/act-02/approve",
        json={"reviewer": "   ", "note": "Nope"},
    )
    assert whitespace_reviewer.status_code == 422


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


def test_upload_hash_is_full_and_limit_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    client.post("/api/cases/case-042/reset")
    monkeypatch.setattr(main_module, "MAX_UPLOAD_BYTES", 4)
    monkeypatch.setattr(main_module, "MAX_UPLOAD_LABEL", "4 bytes")
    too_large = client.post(
        "/api/cases/case-042/evidence",
        files={"file": ("large.txt", b"12345", "text/plain")},
    )
    assert too_large.status_code == 413
    assert "4 bytes" in too_large.json()["detail"]

    accepted = client.post(
        "/api/cases/case-042/evidence",
        files={"file": ("small.txt", b"1234", "text/plain")},
    )
    assert accepted.status_code == 200
    assert len(accepted.json()["evidence"]["content_hash"].removeprefix("sha256:")) == 64


def test_upload_rejects_format_controls_and_overlong_names() -> None:
    client.post("/api/cases/case-042/reset")
    bidi_name = client.post(
        "/api/cases/case-042/evidence",
        files={"file": ("safe\u202etxt", b"nope", "text/plain")},
    )
    assert bidi_name.status_code == 415

    long_name = client.post(
        "/api/cases/case-042/evidence",
        files={"file": ("a" * 252 + ".txt", b"nope", "text/plain")},
    )
    assert long_name.status_code == 415


def test_upload_limit_configuration_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REENTRY_MAX_UPLOAD_BYTES", "-1")
    with pytest.raises(RuntimeError, match="between 1"):
        main_module._configured_upload_limit()

    monkeypatch.setenv("REENTRY_MAX_UPLOAD_BYTES", "not-a-number")
    with pytest.raises(RuntimeError, match="positive integer"):
        main_module._configured_upload_limit()
