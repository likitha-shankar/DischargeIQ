"""
File: dischargeiq/tests/test_main_endpoints.py
Owner: Likitha Shankar
Description: Black-box tests for the FastAPI endpoints other than /chat
  (which is covered by test_chat_grounding) and /analyze (covered indirectly
  by test_er_pipeline + test_api_guardrails).  Validates /health, /pdf,
  /simulator, and /progress contracts via fastapi.testclient.TestClient.
Key functions/classes: test_* functions
Edge cases handled:
  - Unknown session ids → 404 for /pdf and /simulator, not_found body for /progress.
  - Stored entries → 200 with the expected body / content type.
  - Progress TTL eviction (Bug D) — stale entries are swept on /progress reads.
Dependencies: pytest, fastapi.testclient, dischargeiq.main
Called by: pytest (testpaths = dischargeiq/tests per pytest.ini).
"""

import time

import pytest
from fastapi.testclient import TestClient

from dischargeiq import main as dq_main

_client = TestClient(dq_main.app, raise_server_exceptions=True)


# ── /health ────────────────────────────────────────────────────────────────────


def test_health_returns_200_with_expected_keys():
    """Health endpoint always returns 200 and reports provider + DB status."""
    resp = _client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "llm_provider" in body
    assert "anthropic_api_key_configured" in body
    assert "database" in body
    assert isinstance(body["database"], dict)
    assert "configured" in body["database"]


# ── /pdf/{session_id} ──────────────────────────────────────────────────────────


def test_get_pdf_unknown_session_returns_404():
    """Unknown session id → 404 with helpful detail."""
    resp = _client.get("/pdf/unknown-session-id-xyz")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_get_pdf_after_store_returns_bytes_with_correct_content_type():
    """A previously stored PDF can be fetched back with its original bytes."""
    fake_pdf = b"%PDF-1.4 fake pdf body for endpoint test\n%%EOF"
    sid = dq_main._store_pdf(fake_pdf, session_id="test-pdf-roundtrip")
    try:
        resp = _client.get(f"/pdf/{sid}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content == fake_pdf
    finally:
        # Don't pollute the global store across runs.
        with dq_main._pdf_store_lock:
            dq_main._pdf_store.pop(sid, None)


# ── /simulator/{session_id} ────────────────────────────────────────────────────


def test_get_simulator_unknown_session_returns_404():
    """Unknown session id → 404."""
    resp = _client.get("/simulator/unknown-session-id-xyz")
    assert resp.status_code == 404
    assert "no simulator output" in resp.json()["detail"].lower()


def test_get_simulator_after_store_returns_payload():
    """A stored simulator dict is returned verbatim by the endpoint."""
    sid = "test-sim-roundtrip"
    payload = {
        "missed_concepts": [],
        "overall_gap_score": 4,
        "simulator_summary": "Short ER doc with vague follow-up.",
        "fk_grade": 5.5,
        "passes": True,
    }
    with dq_main._pdf_store_lock:
        dq_main._simulator_store[sid] = payload
    try:
        resp = _client.get(f"/simulator/{sid}")
        assert resp.status_code == 200
        assert resp.json() == payload
    finally:
        with dq_main._pdf_store_lock:
            dq_main._simulator_store.pop(sid, None)


# ── /progress/{session_id} ─────────────────────────────────────────────────────


def test_get_progress_unknown_session_returns_not_found_body():
    """
    Unknown session id → 200 with status='not_found' (NOT 404 — the polling
    frontend prefers a body shape it can render uniformly).
    """
    resp = _client.get("/progress/no-such-session-progress")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_found"
    assert body["current_agent"] == 0


def test_get_progress_after_set_returns_progress_payload():
    """An entry written by _set_progress is returned with all its fields."""
    sid = "test-progress-roundtrip"
    dq_main._set_progress(sid, {
        "status": "running",
        "current_agent": 3,
        "agent_name": "Medication",
        "message": "Generating medication explanations…",
    })
    try:
        resp = _client.get(f"/progress/{sid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"
        assert body["current_agent"] == 3
        assert body["agent_name"] == "Medication"
        # The TTL field must be present so the sweeper can find stale entries.
        assert "created_at" in body
    finally:
        dq_main._pipeline_progress.pop(sid, None)


def test_progress_sweep_evicts_stale_entries(monkeypatch):
    """
    Bug D regression: entries older than _PROGRESS_TTL_SECONDS must be evicted
    on the next /progress read so the in-memory dict cannot grow forever.
    """
    sid = "test-progress-stale"
    # Stuff the entry directly with an artificially old timestamp so the sweep
    # will treat it as past TTL.
    dq_main._pipeline_progress[sid] = {
        "status": "complete",
        "current_agent": 7,
        "agent_name": "Complete",
        "message": "Almost ready...",
        "created_at": time.time() - (dq_main._PROGRESS_TTL_SECONDS + 60),
    }
    assert sid in dq_main._pipeline_progress

    # Reading ANY /progress endpoint should sweep stale entries.
    resp = _client.get("/progress/some-other-id")
    assert resp.status_code == 200

    assert sid not in dq_main._pipeline_progress, (
        "Stale entry was not evicted by the TTL sweep on /progress read"
    )
