"""
File: dischargeiq/tests/test_analyze_image.py
Owner: Likitha Shankar
Description: Deterministic tests for the opt-in enhanced scan route
  (POST /analyze/image). Vision transcription and the pipeline are mocked -
  no network, no quota. Covers boundary validation (type, size, page count),
  the too-little-text rejection, and the happy path handoff to the pipeline.
Dependencies: pytest, unittest.mock, fastapi.testclient.
Called by: pytest default run.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from dischargeiq.api import middleware
from dischargeiq.main import app

_client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The 3/min cap on /analyze/image would throttle the suite itself."""
    middleware._rate_windows.clear()
    yield
    middleware._rate_windows.clear()

_JPEG = ("page1.jpg", b"\xff\xd8\xff\xe0fakejpegbytes", "image/jpeg")


def _post(files):
    return _client.post("/analyze/image", files=[("files", f) for f in files])


def test_rejects_non_image_type():
    resp = _post([("doc.pdf", b"%PDF-1.4", "application/pdf")])
    assert resp.status_code == 415


def test_rejects_too_many_pages():
    resp = _post([_JPEG] * 11)
    assert resp.status_code == 422


def test_rejects_oversized_photo():
    big = ("big.jpg", b"x" * (10 * 1024 * 1024 + 1), "image/jpeg")
    resp = _post([big])
    assert resp.status_code == 413


def test_rejects_unreadable_transcription():
    """Vision returns near-nothing -> 422 before any agent call."""
    with patch(
        "dischargeiq.api.routes.analyze.transcribe_document_images",
        return_value="[PAGE 1]\nblur",
    ):
        resp = _post([_JPEG])
    assert resp.status_code == 422
    assert "could not be read" in resp.json()["detail"]


def test_happy_path_hands_transcription_to_pipeline():
    """Good transcription flows into _execute_pipeline as raw_text."""
    transcript = "[PAGE 1]\n" + "Discharge summary. Take furosemide 40mg daily. " * 5
    pipeline_result = {"pipeline_status": "complete", "pdf_session_id": "x"}
    with patch(
        "dischargeiq.api.routes.analyze.transcribe_document_images",
        return_value=transcript,
    ), patch(
        "dischargeiq.api.routes.analyze._execute_pipeline",
        new=AsyncMock(return_value=pipeline_result),
    ) as executed:
        resp = _post([_JPEG])
    assert resp.status_code == 200
    assert resp.json()["pipeline_status"] == "complete"
    assert executed.call_args.kwargs["raw_text"] == transcript


def test_vision_failure_degrades_to_502():
    with patch(
        "dischargeiq.api.routes.analyze.transcribe_document_images",
        side_effect=RuntimeError("quota"),
    ):
        resp = _post([_JPEG])
    assert resp.status_code == 502
    assert "standard scan" in resp.json()["detail"]
