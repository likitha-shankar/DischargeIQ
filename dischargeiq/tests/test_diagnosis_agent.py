"""
File: dischargeiq/tests/test_diagnosis_agent.py
Owner: Likitha Shankar
Description: Black-box tests for Agent 2 (run_diagnosis_agent).  Mocks the
  call_chat_with_fallback path at the agent's import namespace so tests are
  deterministic and offline.  Verifies the public contract: text + fk_grade +
  passes; the retry path on high FK; ValueError on missing primary_diagnosis.
Key functions/classes: test_* functions, _heart_failure_extraction()
Edge cases handled:
  - High-FK first attempt → retry path produces second LLM call.
  - Missing primary_diagnosis → ValueError per the agent's contract.
Dependencies: pytest, unittest.mock, dischargeiq.agents.diagnosis_agent
Called by: pytest (testpaths = dischargeiq/tests per pytest.ini).
"""

from unittest.mock import MagicMock, patch

import pytest

from dischargeiq.agents import diagnosis_agent
from dischargeiq.models.extraction import ExtractionOutput

_MOCK_GET_CLIENT  = "dischargeiq.agents.diagnosis_agent.get_llm_client"
_MOCK_CALL_CHAT   = "dischargeiq.agents.diagnosis_agent.call_chat_with_fallback"
_FAKE_CLIENT_PAIR = (object(), "fake-model")


# ── Helpers ────────────────────────────────────────────────────────────────────


def _heart_failure_extraction() -> ExtractionOutput:
    """Realistic heart-failure ExtractionOutput for happy-path tests."""
    return ExtractionOutput(
        primary_diagnosis="Acute Decompensated Heart Failure",
        secondary_diagnoses=["High blood pressure", "Type 2 Diabetes"],
        procedures_performed=["Diuresis with IV furosemide"],
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_happy_path_returns_text_and_fk_pass():
    """Plain-language explanation → returns text + fk_grade + passes."""
    extraction = _heart_failure_extraction()
    plain_reply = (
        "Your main diagnosis is heart failure. Your heart was not pumping well. "
        "Fluid built up in your lungs. The doctors gave you medicine to help. "
        "You should feel better in a few weeks."
    )
    with patch(_MOCK_GET_CLIENT, return_value=_FAKE_CLIENT_PAIR):
        with patch(_MOCK_CALL_CHAT, return_value=plain_reply):
            result = diagnosis_agent.run_diagnosis_agent(extraction, document_id="hf_01.pdf")

    assert isinstance(result, dict)
    assert set(result) >= {"text", "fk_grade", "passes"}
    assert result["text"] == plain_reply
    assert isinstance(result["fk_grade"], float)
    assert result["passes"] is True, f"Expected pass on plain text, FK={result['fk_grade']}"


def test_high_fk_triggers_retry_path():
    """
    First attempt FK > 6.5 → second attempt fired with simplification suffix.
    The retry only kicks in past the FK retry threshold (6.5), so we use a
    deliberately complex first sentence to force the retry, then a simple
    second one.
    """
    extraction = _heart_failure_extraction()
    complex_reply = (
        "The pathophysiology of decompensated cardiomyopathy involves multifactorial "
        "neurohormonal activation, leading to cumulative hemodynamic deterioration "
        "necessitating intensive pharmacological intervention and continuous monitoring."
    )
    simple_reply = (
        "Your heart was weak. Fluid built up. The doctors gave you medicine. "
        "You should feel better soon."
    )
    call_chat_mock = MagicMock(side_effect=[complex_reply, simple_reply])
    with patch(_MOCK_GET_CLIENT, return_value=_FAKE_CLIENT_PAIR):
        with patch(_MOCK_CALL_CHAT, call_chat_mock):
            result = diagnosis_agent.run_diagnosis_agent(extraction, document_id="hf_01.pdf")

    assert call_chat_mock.call_count == 2, (
        "High-FK first attempt must trigger a retry"
    )
    # Agent picks the lower-FK attempt — retry simpler text wins.
    assert result["text"] == simple_reply


def test_missing_primary_diagnosis_raises_valueerror():
    """Agent 2's LOCKED contract: primary_diagnosis is required."""
    extraction = ExtractionOutput(primary_diagnosis="")
    with patch(_MOCK_GET_CLIENT, return_value=_FAKE_CLIENT_PAIR):
        with patch(_MOCK_CALL_CHAT, return_value="ignored"):
            with pytest.raises(ValueError, match="primary_diagnosis"):
                diagnosis_agent.run_diagnosis_agent(extraction, document_id="missing.pdf")


def test_minimal_extraction_no_secondary_dx_still_works():
    """Only primary_diagnosis present (no secondary, no procedures) → still produces output."""
    extraction = ExtractionOutput(primary_diagnosis="Mild dehydration")
    minimal_reply = (
        "You had mild dehydration. The doctors gave you fluids. You should "
        "feel back to normal in a day or two."
    )
    with patch(_MOCK_GET_CLIENT, return_value=_FAKE_CLIENT_PAIR):
        with patch(_MOCK_CALL_CHAT, return_value=minimal_reply):
            result = diagnosis_agent.run_diagnosis_agent(extraction, document_id="dehydration.pdf")

    assert result["text"] == minimal_reply
    assert isinstance(result["fk_grade"], float)
