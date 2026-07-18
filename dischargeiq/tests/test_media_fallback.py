"""
File: dischargeiq/tests/test_media_fallback.py
Owner: Likitha Shankar
Description: Sprint 6, Task 6.5 - fallback verification. Forces the media
  pipeline to fail three ways and proves (a) it always degrades cleanly (never
  a 500) and (b) the teach-back / comprehension loop is never blocked by a
  media failure. Media serving and quiz scoring are separate routers, so a
  broken explainer cannot take down the headline comprehension metric.
Key functions/classes: test_* functions.
Dependencies: pytest, fastapi.testclient. No LLM calls - /quiz/score is
  deterministic (grades the client-supplied key), so this whole file runs
  offline and fast in the default pytest run.
Called by: pytest default run.
"""

from fastapi.testclient import TestClient

from dischargeiq.api.routes import media
from dischargeiq.main import app

_client = TestClient(app)

# A minimal, valid /quiz/score body. Two questions, both answered correctly.
# Deterministic: no model call, no DB required (persistence is non-fatal).
_QUIZ_SCORE_BODY = {
    "session_id": "media-fallback-test",
    "phase": "pre",
    "question_keys": [
        {"domain": "diagnosis", "correct_index": 0},
        {"domain": "medications", "correct_index": 2},
    ],
    "answers": [0, 2],
}


def _assert_comprehension_loop_alive():
    """The teach-back loop must answer regardless of media state (Task 6.5)."""
    resp = _client.post("/quiz/score", json=_QUIZ_SCORE_BODY)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Both answers correct -> full marks; proves grading ran end to end.
    assert body["score"] == body["total"] == 2
    assert body["percent"] == 100.0


def test_failure_mode_1_missing_artifact(tmp_path, monkeypatch):
    """Mode 1: no media file generated -> clean 404, comprehension loop alive."""
    monkeypatch.setattr(media, "_MEDIA_DIR", tmp_path)  # empty dir
    resp = _client.get("/media/heart_failure")
    assert resp.status_code == 404
    assert "not generated" in resp.json()["detail"].lower()
    assert _client.get("/media/heart_failure/video").status_code == 404
    _assert_comprehension_loop_alive()


def test_failure_mode_2_malformed_artifact(tmp_path, monkeypatch):
    """Mode 2: a corrupt/empty media file exists. The backend serves bytes
    without inspecting them (playback failure is client-side and handled by
    the player's error path); the API must NOT 500. Loop still alive."""
    (tmp_path / "copd.m4a").write_bytes(b"")  # zero-byte / malformed
    (tmp_path / "diabetes.mp4").write_bytes(b"\x00\x01not-a-real-mp4")
    monkeypatch.setattr(media, "_MEDIA_DIR", tmp_path)
    for path in ("/media/copd", "/media/diabetes/video"):
        assert _client.get(path).status_code != 500, f"{path} crashed the API"
    _assert_comprehension_loop_alive()


def test_failure_mode_3_selector_break(tmp_path, monkeypatch):
    """Mode 3: selector/interface break - a bad or hostile document_type
    (unknown label, path traversal) must 404, never 500 or a path lookup.
    Loop still alive."""
    monkeypatch.setattr(media, "_MEDIA_DIR", tmp_path)
    for bad in ("unknown", "..%2F..%2Fetc%2Fpasswd", "heart_failure.m4a", "'; DROP"):
        for suffix in ("", "/video"):
            code = _client.get(f"/media/{bad}{suffix}").status_code
            assert code == 404, f"/media/{bad}{suffix} returned {code}, expected 404"
    _assert_comprehension_loop_alive()


# ── Task 3.3: forced failures on the EXECUTED media path (per-case TTS) ───────
# The three work-plan modes for the generation pipeline: interface break,
# generation timeout, malformed artifact. Contract in every case: a labeled
# 4xx/5xx (never a raw 500 crash), and the teach-back loop keeps scoring.

_CASE_BODY = {
    "session_id": "media-fallback-case",
    "pipeline_payload": {
        "extraction": {"primary_diagnosis": "COPD"},
        "diagnosis_explanation": "Your lungs had a flare-up.",
        "medication_rationale": "Prednisone calms the swelling.",
        "recovery_trajectory": "Week one: rest.",
        "escalation_guide": "Call 911 for severe trouble breathing.",
    },
}


def _clear_audio_cache():
    with media._audio_cache_lock:
        media._audio_cache.clear()
    # /media/case is rate-limited 4/60s per IP; every test in this file
    # shares the "testclient" IP, so clear the window or the later tests
    # measure the limiter instead of the media contract.
    from dischargeiq.api import middleware

    middleware._rate_windows.clear()


def test_case_mode_interface_break(monkeypatch):
    """Script LLM interface break -> labeled 502, loop alive."""
    monkeypatch.setenv("CASE_AUDIO_ENABLED", "true")
    _clear_audio_cache()

    def broken(*a, **k):
        raise RuntimeError("script model interface broke")

    monkeypatch.setattr(media, "build_dialogue_script", broken)
    resp = _client.post("/media/case", json=_CASE_BODY)
    assert resp.status_code == 502
    assert "written summary" in resp.json()["detail"].lower()
    _assert_comprehension_loop_alive()


def test_case_mode_generation_timeout(monkeypatch):
    """TTS timeout -> labeled 502, loop alive."""
    import requests

    monkeypatch.setenv("CASE_AUDIO_ENABLED", "true")
    _clear_audio_cache()
    monkeypatch.setattr(media, "build_dialogue_script", lambda p: "Sam: hi\nAlex: hi")

    def timeout(*a, **k):
        raise requests.Timeout("TTS generation timed out")

    monkeypatch.setattr(media, "synthesize_dialogue_bytes", timeout)
    resp = _client.post("/media/case", json=_CASE_BODY)
    assert resp.status_code == 502
    _assert_comprehension_loop_alive()


def test_case_mode_malformed_artifact_and_flag_off(monkeypatch):
    """Malformed TTS output is served as bytes (client player owns the error
    path, API never 500s); flag off -> 404 identical to a missing file."""
    monkeypatch.setenv("CASE_AUDIO_ENABLED", "true")
    _clear_audio_cache()
    monkeypatch.setattr(media, "build_dialogue_script", lambda p: "Sam: hi\nAlex: hi")
    monkeypatch.setattr(media, "synthesize_dialogue_bytes", lambda s: b"not-a-wav")
    resp = _client.post("/media/case", json=_CASE_BODY)
    assert resp.status_code == 200  # bytes served; playback error is client-side
    _clear_audio_cache()

    monkeypatch.setenv("CASE_AUDIO_ENABLED", "false")
    assert _client.post("/media/case", json=_CASE_BODY).status_code == 404
    _assert_comprehension_loop_alive()


def test_case_audio_cache_hit_skips_generation(monkeypatch):
    """Identical payload -> cached WAV, zero script/TTS calls on repeat."""
    monkeypatch.setenv("CASE_AUDIO_ENABLED", "true")
    _clear_audio_cache()
    calls = {"n": 0}

    def once(p):
        calls["n"] += 1
        return "Sam: hi\nAlex: hi"

    monkeypatch.setattr(media, "build_dialogue_script", once)
    monkeypatch.setattr(media, "synthesize_dialogue_bytes", lambda s: b"RIFFfake")
    first = _client.post("/media/case", json=_CASE_BODY)
    second = _client.post("/media/case", json=_CASE_BODY)
    assert first.status_code == second.status_code == 200
    assert second.content == first.content
    assert calls["n"] == 1, "cache miss on identical payload"
    _clear_audio_cache()
