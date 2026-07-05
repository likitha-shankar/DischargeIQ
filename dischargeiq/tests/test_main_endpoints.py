"""
File: dischargeiq/tests/test_main_endpoints.py
Owner: Likitha Shankar
Description: Black-box tests for the FastAPI endpoints other than /chat
  (covered by test_chat_grounding) and /analyze (covered by test_er_pipeline
  + test_api_guardrails). Validates /health, /pdf, /simulator, and /progress
  contracts via fastapi.testclient.TestClient.

  State is managed via the public SessionStore API (session_store.*) rather
  than poking private attributes on main.py - private attributes are an
  implementation detail that can change without breaking the product contract.

Key functions/classes: test_* functions
Edge cases handled:
  - Unknown session ids → 404 for /pdf and /simulator, not_found body for /progress.
  - Stored entries → 200 with the expected body / content type.
  - Progress TTL eviction (Bug D) - stale entries are swept on /progress reads.
Dependencies: pytest, fastapi.testclient, dischargeiq.main (for app + backward-compat),
  dischargeiq.services.session (for test state setup)
Called by: pytest (testpaths = dischargeiq/tests per pytest.ini).
"""

import time

import pytest
from fastapi.testclient import TestClient

from dischargeiq.main import app
from dischargeiq.services.session import _PROGRESS_TTL_SECONDS, session_store

_client = TestClient(app, raise_server_exceptions=True)


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
    sid = session_store.store_pdf(fake_pdf, session_id="test-pdf-roundtrip")
    try:
        resp = _client.get(f"/pdf/{sid}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content == fake_pdf
    finally:
        with session_store._pdf_lock:
            session_store._pdf.pop(sid, None)


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
    session_store.store_simulator(sid, payload)
    try:
        resp = _client.get(f"/simulator/{sid}")
        assert resp.status_code == 200
        assert resp.json() == payload
    finally:
        with session_store._simulator_lock:
            session_store._simulator.pop(sid, None)


# ── /progress/{session_id} ─────────────────────────────────────────────────────


def test_get_progress_unknown_session_returns_not_found_body():
    """
    Unknown session id → 200 with status='not_found' (NOT 404 - the polling
    frontend prefers a body shape it can render uniformly).
    """
    resp = _client.get("/progress/no-such-session-progress")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_found"
    assert body["current_agent"] == 0


def test_get_progress_after_set_returns_progress_payload():
    """An entry written by set_progress is returned with all its fields."""
    sid = "test-progress-roundtrip"
    session_store.set_progress(sid, {
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
        session_store.pop_progress(sid)


def test_progress_sweep_evicts_stale_entries():
    """
    Bug D regression: entries older than progress_ttl must be evicted on
    the next /progress read so the in-memory dict cannot grow forever.
    """
    sid = "test-progress-stale"
    # Inject an artificially old timestamp so sweep_stale_progress() treats
    # this entry as expired without having to wait 600 real seconds.
    with session_store._progress_lock:
        session_store._progress[sid] = {
            "status": "complete",
            "current_agent": 7,
            "agent_name": "Complete",
            "message": "Almost ready...",
            "created_at": time.time() - (_PROGRESS_TTL_SECONDS + 60),
        }
    assert session_store.get_progress(sid) is not None

    # Any /progress read sweeps stale entries as a side effect.
    resp = _client.get("/progress/some-other-id")
    assert resp.status_code == 200

    assert session_store.get_progress(sid) is None, (
        "Stale entry was not evicted by the TTL sweep on /progress read"
    )
