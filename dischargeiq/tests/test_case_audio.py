"""
File: dischargeiq/tests/test_case_audio.py
Owner: Likitha Shankar
Description: Deterministic tests for the per-case audio prototype (Task 2.5).
  LLM and TTS calls are mocked - no network, no quota. Covers script
  generation (payload -> dialogue), the empty-payload and bad-script guards,
  and the PCM-to-WAV wrapper written by synthesize_dialogue.
Dependencies: pytest, unittest.mock.
Called by: pytest default run.
"""

import base64
import struct
from unittest.mock import patch

import pytest

from dischargeiq.utils import case_audio

_PAYLOAD = {
    "extraction": {"primary_diagnosis": "Heart failure", "medications": [{"name": "Furosemide", "dose": "40mg"}]},
    "diagnosis_explanation": "Your heart was not pumping blood the way it should.",
    "medication_rationale": "Furosemide removes extra fluid.",
    "recovery_trajectory": "Rest this week.",
    "escalation_guide": "Call your doctor for fast weight gain.",
    "document_type": "heart_failure",
}

_SCRIPT = (
    "Sam: Welcome home. Let's talk about what happened.\n"
    "Alex: Your heart was not pumping blood the way it should.\n"
    "Sam: Your water pill removes the extra fluid.\n"
)


def test_build_dialogue_script_happy_path():
    """Payload flows to the LLM; a Sam/Alex script comes back unchanged."""
    with patch.object(case_audio, "get_llm_client", return_value=(object(), "model-x")), \
         patch.object(case_audio, "call_chat_with_fallback", return_value=_SCRIPT) as chat:
        script = case_audio.build_dialogue_script(_PAYLOAD)
    assert script == _SCRIPT.strip()
    # The user message must carry the care plan - grounding contract.
    assert "Furosemide" in chat.call_args.kwargs["user_message"]


def test_build_dialogue_script_rejects_empty_payload():
    """No content -> ValueError before any model call (quota protection)."""
    with pytest.raises(ValueError):
        case_audio.build_dialogue_script({})


def test_build_dialogue_script_rejects_scriptless_reply():
    """A reply with no speaker lines is unusable and must raise."""
    with patch.object(case_audio, "get_llm_client", return_value=(object(), "m")), \
         patch.object(case_audio, "call_chat_with_fallback", return_value="sorry, no"):
        with pytest.raises(ValueError):
            case_audio.build_dialogue_script(_PAYLOAD)


def test_synthesize_dialogue_writes_valid_wav(tmp_path, monkeypatch):
    """Mocked TTS PCM lands on disk as a well-formed 24 kHz mono WAV."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    pcm = b"\x00\x01" * 2400  # 0.1 s of fake PCM

    class _Resp:
        status_code = 200

        def raise_for_status(self):  # noqa: D102 - test double
            pass

        def json(self):  # noqa: D102 - test double
            return {"candidates": [{"content": {"parts": [{"inlineData": {
                "mimeType": "audio/L16;codec=pcm;rate=24000",
                "data": base64.b64encode(pcm).decode(),
            }}]}}]}

    with patch.object(case_audio.requests, "post", return_value=_Resp()) as post:
        out = case_audio.synthesize_dialogue(_SCRIPT, tmp_path / "case.wav")

    raw = out.read_bytes()
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE"
    # Sample rate field in the fmt chunk must be 24000.
    assert struct.unpack("<I", raw[24:28])[0] == 24000
    assert raw[44:] == pcm  # payload untouched after the 44-byte header
    # Multi-speaker config with both hosts went out in the request body.
    body = post.call_args.kwargs["json"]
    speakers = {c["speaker"] for c in body["generationConfig"]["speechConfig"]
                ["multiSpeakerVoiceConfig"]["speakerVoiceConfigs"]}
    assert speakers == {"Sam", "Alex"}


# ── POST /media/case serving path (decision D-5: on-demand, flag-gated) ──────

from fastapi.testclient import TestClient  # noqa: E402

from dischargeiq.main import app  # noqa: E402

_client = TestClient(app)

_CASE_BODY = {"session_id": "case-audio-test", "pipeline_payload": _PAYLOAD}


def test_media_case_404_when_flag_off(monkeypatch):
    """Flag off must look exactly like 'no media file': 404, text fallback."""
    monkeypatch.delenv("CASE_AUDIO_ENABLED", raising=False)
    resp = _client.post("/media/case", json=_CASE_BODY)
    assert resp.status_code == 404


def test_media_case_returns_wav_when_enabled(monkeypatch):
    """Flag on + both model calls mocked -> WAV bytes with audio/wav type."""
    monkeypatch.setenv("CASE_AUDIO_ENABLED", "true")
    fake_wav = b"RIFF....WAVEfmt fake"
    from dischargeiq.api.routes import media as media_route

    with patch.object(media_route, "build_dialogue_script", return_value=_SCRIPT), \
         patch.object(media_route, "synthesize_dialogue_bytes", return_value=fake_wav):
        resp = _client.post("/media/case", json=_CASE_BODY)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    assert resp.content == fake_wav


def test_media_case_422_on_empty_payload(monkeypatch):
    """Nothing to narrate -> 422 before any model call is attempted."""
    monkeypatch.setenv("CASE_AUDIO_ENABLED", "1")
    resp = _client.post(
        "/media/case",
        json={"session_id": "s", "pipeline_payload": {}},
    )
    assert resp.status_code == 422


def test_media_case_502_when_tts_fails(monkeypatch):
    """Model/TTS failure degrades to 502 with a text-fallback message, not 500."""
    monkeypatch.setenv("CASE_AUDIO_ENABLED", "1")
    from dischargeiq.api.routes import media as media_route

    with patch.object(media_route, "build_dialogue_script", return_value=_SCRIPT), \
         patch.object(
             media_route, "synthesize_dialogue_bytes",
             side_effect=RuntimeError("quota exhausted"),
         ):
        resp = _client.post("/media/case", json=_CASE_BODY)
    assert resp.status_code == 502
    assert "written summary" in resp.json()["detail"]
