"""
File: dischargeiq/tests/test_er_pipeline.py
Owner: Likitha Shankar
Description: Regression tests verifying the full pipeline handles ER-style minimal
  discharge inputs without returning pipeline_status="partial". ER documents are
  shorter and simpler than inpatient discharges -- fewer fields, shorter medication
  lists, vague follow-up -- and are the expected format for the AMAP/emopti dataset.
  All LLM calls are mocked so no API keys are needed.
Key functions/classes: test_* functions, _er_extraction(), _er_pipeline_context()
Edge cases handled:
  - Minimal extraction (1 medication, 1 appointment, short doc) must not partial.
  - Empty medication list (laceration-only) must not partial.
  - Agent 6 fallback on empty concepts must not partial.
Dependencies: pytest, unittest.mock, fastapi.testclient, dischargeiq.pipeline.orchestrator,
  dischargeiq.models.extraction, dischargeiq.models.pipeline
Called by: pytest (testpaths = dischargeiq/tests per pytest.ini).
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dischargeiq.models.extraction import ExtractionOutput, FollowUpAppointment, Medication
from dischargeiq.models.pipeline import PatientSimulatorOutput, PipelineResponse
from dischargeiq.pipeline import orchestrator

# ── Mock targets ───────────────────────────────────────────────────────────────
# Patch at the orchestrator's import namespace so asyncio.to_thread
# picks up the mock rather than the real function.
_MOCK_EXTRACT_TEXT    = "dischargeiq.pipeline.orchestrator.extract_text_from_pdf"
_MOCK_RUN_EXTRACTION  = "dischargeiq.pipeline.orchestrator.run_extraction_agent"
_MOCK_RUN_DIAGNOSIS   = "dischargeiq.pipeline.orchestrator.run_diagnosis_agent"
_MOCK_RUN_MEDICATION  = "dischargeiq.pipeline.orchestrator.run_medication_agent"
_MOCK_RUN_RECOVERY    = "dischargeiq.pipeline.orchestrator.run_recovery_agent"
_MOCK_RUN_ESCALATION  = "dischargeiq.pipeline.orchestrator.run_escalation_agent"
_MOCK_RUN_SIMULATOR   = "dischargeiq.pipeline.orchestrator.run_patient_simulator_agent"
# DB write is non-fatal but hits the network; mock it out unconditionally.
_MOCK_SAVE_HISTORY    = "dischargeiq.pipeline.orchestrator._save_history_with_retries"

# ── ER extraction stubs ────────────────────────────────────────────────────────


def _laceration_extraction() -> ExtractionOutput:
    """Minimal ExtractionOutput for a simple finger-laceration ER visit."""
    return ExtractionOutput(
        primary_diagnosis="Laceration, right index finger — repaired with 3 sutures",
        medications=[
            Medication(name="Ibuprofen", dose="400mg", frequency="as needed up to 3 times daily")
        ],
        follow_up_appointments=[
            FollowUpAppointment(provider="Primary care doctor", date="7-10 days")
        ],
        red_flag_symptoms=[
            "increasing redness or swelling",
            "pus from wound",
            "fever above 38.5C",
        ],
        activity_restrictions=["avoid heavy gripping"],
        dietary_restrictions=[],
    )


def _asthma_extraction() -> ExtractionOutput:
    """Minimal ExtractionOutput for a mild asthma exacerbation ER visit."""
    return ExtractionOutput(
        primary_diagnosis="Mild asthma exacerbation",
        medications=[
            Medication(name="Albuterol inhaler", dose="2 puffs", frequency="every 4-6 hours as needed"),
            Medication(name="Prednisone", dose="40mg", frequency="once daily for 5 days", status="new"),
        ],
        follow_up_appointments=[
            FollowUpAppointment(provider="Your doctor", date="as soon as possible")
        ],
        red_flag_symptoms=[
            "severe shortness of breath not relieved by inhaler",
            "lips or fingernails turning blue",
            "cannot speak in full sentences",
        ],
        activity_restrictions=[],
        dietary_restrictions=[],
    )


def _agent_text_result(text: str) -> dict:
    """Minimal agent text result dict (text, fk_grade, passes)."""
    return {"text": text, "fk_grade": 5.0, "passes": True}


def _minimal_simulator_output() -> PatientSimulatorOutput:
    """Minimal (but valid) PatientSimulatorOutput for ER docs."""
    return PatientSimulatorOutput(
        missed_concepts=[],
        overall_gap_score=7,
        simulator_summary="Short ER discharge — follow-up timing and wound care are not fully specified.",
        fk_grade=5.5,
        passes=True,
    )


# ── Helper to run the async orchestrator in sync tests ─────────────────────────


def _run_pipeline(pdf_path: str = "er_test.pdf") -> PipelineResponse:
    """Run run_pipeline synchronously via asyncio.run."""
    return asyncio.run(orchestrator.run_pipeline(pdf_path))


# ── Shared patch context for both ER tests ─────────────────────────────────────


def _er_patches(extraction: ExtractionOutput):
    """Return a list of patch context managers for a full mocked pipeline run."""
    return [
        patch(_MOCK_EXTRACT_TEXT, return_value="ER discharge text — minimal content"),
        patch(_MOCK_RUN_EXTRACTION, return_value=extraction),
        patch(_MOCK_RUN_DIAGNOSIS,  return_value=_agent_text_result("You had a minor injury that was repaired.")),
        patch(_MOCK_RUN_MEDICATION, return_value=_agent_text_result("Take ibuprofen for pain as needed.")),
        patch(_MOCK_RUN_RECOVERY,   return_value=_agent_text_result("Keep wound clean and dry for 24 hours.")),
        patch(_MOCK_RUN_ESCALATION, return_value=_agent_text_result("Go to the ER if the wound looks infected.")),
        patch(_MOCK_RUN_SIMULATOR,  return_value=_minimal_simulator_output()),
        patch(_MOCK_SAVE_HISTORY,   new_callable=AsyncMock),
    ]


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_laceration_er_pipeline_is_not_partial():
    """
    A minimal laceration ER extraction must produce complete or complete_with_warnings.
    pipeline_status must never be "partial" when all mocked agents return valid output.
    """
    extraction = _laceration_extraction()
    patches = _er_patches(extraction)

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
        result = _run_pipeline("er_laceration_01.pdf")

    assert result.pipeline_status in ("complete", "complete_with_warnings"), (
        f"Expected complete/complete_with_warnings, got '{result.pipeline_status}'"
    )
    assert result.diagnosis_explanation != ""
    assert result.medication_rationale != ""
    assert result.escalation_guide != ""


def test_asthma_er_pipeline_is_not_partial():
    """
    A minimal asthma ER extraction must produce complete or complete_with_warnings.
    Tests a 2-medication ER doc with a steroid course and vague follow-up.
    """
    extraction = _asthma_extraction()
    patches = _er_patches(extraction)

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
        result = _run_pipeline("er_asthma_01.pdf")

    assert result.pipeline_status in ("complete", "complete_with_warnings"), (
        f"Expected complete/complete_with_warnings, got '{result.pipeline_status}'"
    )
    assert result.diagnosis_explanation != ""
    assert result.escalation_guide != ""
    assert result.patient_simulator is not None
    assert result.patient_simulator.overall_gap_score >= 0


def test_er_pipeline_with_empty_medications_does_not_partial():
    """
    An ER extraction with no medications (e.g. wound care only) must not partial.
    This guards against agents that crash on an empty medication list.
    """
    extraction = ExtractionOutput(
        primary_diagnosis="Minor contusion, left knee — no treatment required",
        medications=[],
        follow_up_appointments=[
            FollowUpAppointment(provider="Primary care", date="if symptoms worsen")
        ],
        red_flag_symptoms=["severe swelling", "inability to bear weight"],
        activity_restrictions=["avoid running for 1 week"],
        dietary_restrictions=[],
    )
    patches = _er_patches(extraction)

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
        result = _run_pipeline("er_contusion.pdf")

    assert result.pipeline_status in ("complete", "complete_with_warnings"), (
        f"Expected complete/complete_with_warnings for no-medication ER doc, "
        f"got '{result.pipeline_status}'"
    )


def test_er_pipeline_simulator_fallback_does_not_partial():
    """
    When Agent 6 returns a zero-score fallback (empty concepts), the pipeline
    status must still be complete or complete_with_warnings — never partial.
    """
    empty_sim = PatientSimulatorOutput(
        missed_concepts=[],
        overall_gap_score=0,
        simulator_summary="",
        fk_grade=0.0,
        passes=False,
    )
    extraction = _laceration_extraction()
    patches = _er_patches(extraction)
    # Override the simulator patch with one that returns the empty fallback.
    patches[6] = patch(_MOCK_RUN_SIMULATOR, return_value=empty_sim)

    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
        result = _run_pipeline("er_laceration_fallback.pdf")

    assert result.pipeline_status in ("complete", "complete_with_warnings"), (
        f"Agent 6 fallback should not cause partial status, got '{result.pipeline_status}'"
    )
    assert result.patient_simulator is not None
    assert result.patient_simulator.missed_concepts == []
