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

import json
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


# ── Chat context resolution (July 2026: server-side context cache) ────────────


def _fake_answer(message, pipeline_context):
    """Stand-in for ChatService.answer - echoes which context it received."""
    return (
        f"echo:{pipeline_context.get('diagnosis_explanation', '')}",
        None,
        True,
    )


def test_chat_uses_server_cached_context(monkeypatch):
    """POST /chat with only session_id must ground from the /analyze cache."""
    from dischargeiq.services.chat import chat_service

    sid = "test-chat-ctx"
    session_store.store_context(sid, {"diagnosis_explanation": "cached-ctx"})
    monkeypatch.setattr(chat_service, "answer", _fake_answer)
    try:
        resp = _client.post("/chat", json={"message": "hi", "session_id": sid})
        assert resp.status_code == 200
        assert resp.json()["reply"] == "echo:cached-ctx"
    finally:
        with session_store._context_lock:
            session_store._context.pop(sid, None)


def test_chat_falls_back_to_request_context(monkeypatch):
    """Evicted session + client-sent pipeline_context must still answer."""
    from dischargeiq.services.chat import chat_service

    monkeypatch.setattr(chat_service, "answer", _fake_answer)
    resp = _client.post("/chat", json={
        "message": "hi",
        "session_id": "test-chat-missing",
        "pipeline_context": {"diagnosis_explanation": "client-ctx"},
    })
    assert resp.status_code == 200
    assert resp.json()["reply"] == "echo:client-ctx"


def test_chat_without_any_context_returns_409():
    """No cache entry and no request context - client must re-analyze."""
    resp = _client.post("/chat", json={
        "message": "hi", "session_id": "test-chat-none",
    })
    assert resp.status_code == 409


def test_chat_stream_emits_deltas_then_done(monkeypatch):
    """/chat/stream must yield SSE delta events and one final done event."""
    from dischargeiq.services.chat import chat_service

    def fake_stream(message, pipeline_context):
        yield "delta", "Hello "
        yield "delta", "there."
        yield "done", {"reply": "Hello there.", "source_page": None,
                       "from_document": True}

    monkeypatch.setattr(chat_service, "answer_stream", fake_stream)
    sid = "test-chat-stream"
    session_store.store_context(sid, {"diagnosis_explanation": "x"})
    try:
        with _client.stream(
            "POST", "/chat/stream", json={"message": "hi", "session_id": sid}
        ) as resp:
            assert resp.status_code == 200
            events = [
                json.loads(line[len("data: "):])
                for line in resp.iter_lines()
                if line.startswith("data: ")
            ]
        assert [e.get("delta") for e in events[:2]] == ["Hello ", "there."]
        assert events[-1]["done"] is True
        assert events[-1]["reply"] == "Hello there."
    finally:
        with session_store._context_lock:
            session_store._context.pop(sid, None)


# ── Token-usage reductions (July 2026): hash cache + context pruning ──────────


def test_result_hash_cache_roundtrip_and_eviction():
    """store_result_for_hash caches per hash and evicts oldest at capacity."""
    from dischargeiq.services.session import _PDF_STORE_MAX

    payload = {"pipeline_status": "complete", "extraction": {"a": 1}}
    session_store.store_result_for_hash("hash-test-1", payload)
    assert session_store.get_result_for_hash("hash-test-1") == payload
    try:
        # Fill to capacity: the first entry must be evicted, newest kept.
        for i in range(_PDF_STORE_MAX):
            session_store.store_result_for_hash(f"hash-test-fill-{i}", {"i": i})
        assert session_store.get_result_for_hash("hash-test-1") is None
        assert session_store.get_result_for_hash(
            f"hash-test-fill-{_PDF_STORE_MAX - 1}") == {"i": _PDF_STORE_MAX - 1}
    finally:
        with session_store._result_lock:
            session_store._result_by_hash.clear()


def test_prune_empty_drops_nulls_keeps_real_falsy():
    """_prune_empty removes null/empty members but keeps False and 0."""
    from dischargeiq.services.chat import _prune_empty

    extraction = {
        "patient_name": None,
        "primary_diagnosis": "COPD",
        "secondary_diagnoses": [],
        "medications": [
            {"name": "Prednisone", "dose": "40mg", "duration": None},
        ],
        "answered": False,
        "count": 0,
        "nested": {"empty": "", "inner": {}},
    }
    pruned = _prune_empty(extraction)
    assert pruned == {
        "primary_diagnosis": "COPD",
        "medications": [{"name": "Prednisone", "dose": "40mg"}],
        "answered": False,
        "count": 0,
    }


def test_analyze_text_serves_cache_hit_under_new_session():
    """
    Second upload of identical text must skip the pipeline entirely and
    return the cached result stamped with the NEW session id.
    """
    import hashlib

    text = "Synthetic discharge text for the hash-cache endpoint test. " * 20
    # The route hashes the STRIPPED text - mirror it exactly, or the lookup
    # misses and the test burns a real 7-call pipeline run.
    doc_hash = hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
    cached = {
        "pipeline_status": "complete",
        "extraction": {"primary_diagnosis": "COPD"},
        "patient_simulator": None,
        "pdf_session_id": "old-session",
    }
    session_store.store_result_for_hash(doc_hash, cached)
    try:
        resp = _client.post(
            "/analyze/text",
            json={"text": text},
            headers={"X-Discharge-Session-Id": "cache-hit-session"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["pipeline_status"] == "complete"
        assert body["pdf_session_id"] != "old-session"
        # The new session must be chat-ready from the cached context.
        assert session_store.get_context(body["pdf_session_id"]) is not None
    finally:
        with session_store._result_lock:
            session_store._result_by_hash.pop(doc_hash, None)
        with session_store._context_lock:
            session_store._context.pop("cache-hit-session", None)
