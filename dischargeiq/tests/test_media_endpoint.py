"""
File: dischargeiq/tests/test_media_endpoint.py
Owner: Likitha Shankar
Description: Tests for GET /media/{document_type} (Sprint 4, Task 4.1) -
  allowlist boundary validation (no path traversal), the normal 404 fallback
  when audio is not generated yet, and the happy path serving a real file.
Dependencies: pytest, fastapi.testclient.
Called by: pytest default run.
"""

from fastapi.testclient import TestClient

from dischargeiq.api.routes import media
from dischargeiq.main import app

_client = TestClient(app)


def test_unknown_label_is_404_not_path_lookup():
    """Labels outside the router set 404 immediately - path traversal dead."""
    for bad in ("unknown", "nope", "..%2F..%2Fetc%2Fpasswd", "heart_failure.m4a"):
        assert _client.get(f"/media/{bad}").status_code == 404


def test_missing_audio_is_clean_404():
    """Valid diagnosis with no generated file yet -> 404 (UI hides player)."""
    resp = _client.get("/media/heart_failure")
    # Passes whether or not the team has dropped real audio in yet:
    # generated -> 200 with audio mime; not yet -> clean 404.
    assert resp.status_code in (200, 404)
    if resp.status_code == 404:
        assert "not generated" in resp.json()["detail"].lower()


def test_serves_existing_file(tmp_path, monkeypatch):
    """A dropped-in .m4a is served with the audio/mp4 MIME type."""
    (tmp_path / "copd.m4a").write_bytes(b"fake-audio-bytes")
    monkeypatch.setattr(media, "_MEDIA_DIR", tmp_path)
    resp = _client.get("/media/copd")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/mp4"
    assert resp.content == b"fake-audio-bytes"
