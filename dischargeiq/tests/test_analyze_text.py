"""
File: dischargeiq/tests/test_analyze_text.py
Owner: Likitha Shankar
Description: Deterministic tests for POST /analyze/text (Sprint 2, Task 2.3 -
  mobile on-device OCR path). Pipeline agents are mocked; verifies the raw_text
  path skips PDF reading entirely, tags the ingest as ocr_photo (scan-quality
  warning), and validates text length limits.
Key functions/classes: test_* functions
Dependencies: pytest, fastapi.testclient, unittest.mock, dischargeiq.main
Called by: pytest default run (not marked slow).
"""

import json
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from dischargeiq.main import app
from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.models.pipeline import PatientSimulatorOutput

_client = TestClient(app)

_OCR_TEXT = (
    "DISCHARGE SUMMARY\n"
    "Primary Diagnosis: Congestive heart failure with reduced ejection fraction.\n"
    "Medications: Furosemide 40mg once daily in the morning.\n"
    "Follow up with cardiology in 2 weeks. Weigh yourself every morning.\n"
    "Call your doctor for weight gain over 3 pounds in one day."
)


def _mock_patches():
    """Patch every agent at the orchestrator namespace, like the ER tests."""
    return [
        patch(
            "dischargeiq.pipeline.orchestrator.run_router_agent",
            return_value={"document_type": "heart_failure", "confidence": 0.95,
                          "should_process": True, "reason": "mocked"},
        ),
        patch(
            "dischargeiq.pipeline.orchestrator.run_extraction_agent",
            return_value=ExtractionOutput(
                primary_diagnosis="Heart failure",
                red_flag_symptoms=["weight gain over 3 pounds in one day"],
            ),
        ),
        patch("dischargeiq.pipeline.orchestrator.run_diagnosis_agent",
              return_value={"text": "Your heart was weak.", "fk_grade": 4.0, "passes": True}),
        patch("dischargeiq.pipeline.orchestrator.run_medication_agent",
              return_value={"text": "Take your water pill.", "fk_grade": 4.0, "passes": True}),
        patch("dischargeiq.pipeline.orchestrator.run_recovery_agent",
              return_value={"text": "Rest this week.", "fk_grade": 4.0, "passes": True}),
        patch("dischargeiq.pipeline.orchestrator.run_escalation_agent",
              return_value={"text": "Call if you gain weight fast.", "fk_grade": 4.0, "passes": True}),
        patch("dischargeiq.pipeline.orchestrator.run_patient_simulator_agent",
              return_value=PatientSimulatorOutput(
                  missed_concepts=[], overall_gap_score=2,
                  simulator_summary="Looks clear.", fk_grade=5.0, passes=True)),
        patch("dischargeiq.pipeline.orchestrator._save_history_with_retries",
              new_callable=AsyncMock),
        # Must NEVER be called on the text path - there is no file to read.
        patch("dischargeiq.pipeline.orchestrator.extract_document_text",
              side_effect=AssertionError("extract_document_text called on raw_text path")),
    ]


def test_analyze_text_runs_pipeline_without_touching_disk():
    """OCR text goes through the full pipeline; pdfplumber path never runs."""
    with ExitStack() as stack:
        for p in _mock_patches():
            stack.enter_context(p)
        resp = _client.post("/analyze/text", json={"text": _OCR_TEXT})

    assert resp.status_code == 200
    body = resp.json()
    assert body["pipeline_status"] in ("complete", "complete_with_warnings")
    assert body["extraction"]["primary_diagnosis"] == "Heart failure"
    assert body["pdf_session_id"]
    # The scan-quality note rides the standard warnings channel.
    assert any("camera scan" in w for w in body["extraction_warnings"])


def test_analyze_text_rejects_too_short():
    """A failed scan (near-empty text) is a 422 with retake guidance."""
    resp = _client.post("/analyze/text", json={"text": "blurry"})
    assert resp.status_code == 422
    assert "Retake" in resp.json()["detail"]


def test_analyze_text_rejects_too_long():
    resp = _client.post("/analyze/text", json={"text": "x" * 200_001})
    assert resp.status_code == 422
