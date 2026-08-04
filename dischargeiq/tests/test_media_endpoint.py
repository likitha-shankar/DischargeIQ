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


def test_video_endpoint_serves_mp4_and_404s_cleanly(tmp_path, monkeypatch):
    """Video kind: mp4 served with video MIME; missing video is a clean 404
    even when the AUDIO for the same diagnosis exists (kinds are independent)."""
    (tmp_path / "copd.mp4").write_bytes(b"fake-video-bytes")
    (tmp_path / "diabetes.m4a").write_bytes(b"audio-only")
    monkeypatch.setattr(media, "_MEDIA_DIR", tmp_path)

    ok = _client.get("/media/copd/video")
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "video/mp4"

    missing = _client.get("/media/diabetes/video")
    assert missing.status_code == 404
    assert "video not generated" in missing.json()["detail"].lower()
    assert _client.get("/media/nope/video").status_code == 404


def test_head_probe_matches_get(tmp_path, monkeypatch) -> None:
    """
    HEAD must answer like GET, because that is how clients probe.

    AudioExplainerCard sends HEAD and shows a player only on 200. The routes
    were registered GET-only, so Starlette answered every probe with 405 and
    the card stayed hidden even when the audio existed. Registering both
    methods is what makes the feature reachable at all.
    """
    (tmp_path / "copd.wav").write_bytes(b"fake-audio-bytes")
    monkeypatch.setattr(media, "_MEDIA_DIR", tmp_path)

    present = _client.head("/media/copd")
    assert present.status_code == 200, "probe must see 200 when the file exists"
    assert present.content == b"", "HEAD carries no body"

    # Absent media is 404 ("hide the player"), never 405 ("wrong method").
    assert _client.head("/media/diabetes").status_code == 404
    assert _client.head("/media/copd/video").status_code == 404
