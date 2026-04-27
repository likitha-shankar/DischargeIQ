"""
File: dischargeiq/tests/test_medication_agent.py
Owner: Likitha Shankar
Description: Black-box tests for Agent 3 (run_medication_agent).  All LLM calls
  are mocked at the module's _get_client target so tests are deterministic and
  do not require an Anthropic API key.  Verifies the public contract: text +
  fk_grade + passes; the no-medications fallback; the discontinued-medication
  paragraph format; and crash behaviour on missing primary_diagnosis.
Key functions/classes: test_* functions, _fake_client(), _heart_failure_extraction()
Edge cases handled:
  - Empty medication list → special two-sentence fallback rendered verbatim.
  - LLM returns empty content → graceful empty-string output, FK check still runs.
  - Missing primary_diagnosis → ValueError per the documented contract.
Dependencies: pytest, unittest.mock, dischargeiq.agents.medication_agent,
  dischargeiq.models.extraction
Called by: pytest (testpaths = dischargeiq/tests per pytest.ini).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from dischargeiq.agents import medication_agent
from dischargeiq.models.extraction import ExtractionOutput, Medication

_MOCK_CLIENT_TARGET = "dischargeiq.agents.medication_agent._get_client"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _fake_anthropic_response(text: str):
    """Build a fake Anthropic .messages.create() response carrying `text`."""
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


def _fake_client(reply_text: str) -> MagicMock:
    """Return a MagicMock client whose .messages.create() returns reply_text."""
    client = MagicMock()
    client.messages.create.return_value = _fake_anthropic_response(reply_text)
    return client


def _heart_failure_extraction() -> ExtractionOutput:
    """3-medication heart-failure ExtractionOutput used by happy-path tests."""
    return ExtractionOutput(
        primary_diagnosis="Acute Decompensated Heart Failure",
        medications=[
            Medication(name="Furosemide", dose="40mg", frequency="once daily", status="new"),
            Medication(name="Lisinopril", dose="20mg", frequency="once daily", status="new"),
            Medication(name="Carvedilol", dose="12.5mg", frequency="twice daily", status="continued"),
        ],
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_happy_path_returns_text_fk_passes():
    """Three medications → non-empty text + fk grade + passes flag."""
    extraction = _heart_failure_extraction()
    reply = (
        "Furosemide:\nThis medicine helps your body remove extra fluid. You may "
        "urinate more often. Call your doctor if you feel very dizzy.\n\n"
        "Lisinopril:\nThis medicine helps your heart pump more easily. You may "
        "feel a dry cough. Call your doctor if your face swells.\n\n"
        "Carvedilol:\nThis medicine slows your heart rate. You may feel tired "
        "at first. Call your doctor if you feel faint."
    )
    with patch(_MOCK_CLIENT_TARGET, return_value=_fake_client(reply)):
        result = medication_agent.run_medication_agent(extraction, document_id="hf_01.pdf")

    assert isinstance(result, dict)
    assert set(result) >= {"text", "fk_grade", "passes"}
    assert result["text"] != ""
    assert "Furosemide" in result["text"]
    assert isinstance(result["fk_grade"], float)
    assert isinstance(result["passes"], bool)


def test_empty_medication_list_renders_no_meds_fallback():
    """
    No medications: per agent3_system_prompt.txt the LLM is told to output
    exactly two sentences.  We mock the LLM with that exact verbatim output
    and verify the agent passes it through without modification.
    """
    extraction = ExtractionOutput(
        primary_diagnosis="Minor laceration, finger — repaired",
        medications=[],
    )
    no_meds_reply = (
        "Your doctor did not prescribe any medicines for you to take at home. "
        "Ask your doctor if you need to start any medicines at your follow-up visit."
    )
    with patch(_MOCK_CLIENT_TARGET, return_value=_fake_client(no_meds_reply)):
        result = medication_agent.run_medication_agent(extraction, document_id="laceration.pdf")

    assert no_meds_reply in result["text"]
    assert "doctor did not prescribe any medicines" in result["text"]


def test_discontinued_medication_uses_stopping_format():
    """
    A medication with status='discontinued' must produce the [Drug name] -
    stopping: format (the LLM is the one that generates this — we just verify
    the agent passes through the formatted reply).
    """
    extraction = ExtractionOutput(
        primary_diagnosis="Atrial Fibrillation",
        medications=[
            Medication(name="Warfarin", dose="5mg", frequency="once daily", status="discontinued"),
        ],
    )
    stopping_reply = (
        "Warfarin — stopping:\n"
        "Your doctor wants you to stop taking this medicine.\n"
        "Your bleeding risk was too high on this drug.\n"
        "Do not take it until your doctor tells you it is safe to start again."
    )
    with patch(_MOCK_CLIENT_TARGET, return_value=_fake_client(stopping_reply)):
        result = medication_agent.run_medication_agent(extraction, document_id="afib.pdf")

    assert "stopping" in result["text"].lower()
    assert "Warfarin" in result["text"]


def test_missing_primary_diagnosis_raises_valueerror():
    """Agent 3's LOCKED contract: primary_diagnosis is required."""
    extraction = ExtractionOutput(
        primary_diagnosis="",
        medications=[Medication(name="Aspirin", dose="81mg")],
    )
    with patch(_MOCK_CLIENT_TARGET, return_value=_fake_client("ignored")):
        with pytest.raises(ValueError, match="primary_diagnosis"):
            medication_agent.run_medication_agent(extraction, document_id="missing_dx.pdf")


def test_empty_anthropic_content_returns_empty_text_no_crash():
    """
    Bug C regression: when Anthropic returns content=[], the new guard makes the
    agent return an empty rationale_text instead of crashing with IndexError.
    """
    extraction = _heart_failure_extraction()
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(content=[])
    with patch(_MOCK_CLIENT_TARGET, return_value=client):
        result = medication_agent.run_medication_agent(extraction, document_id="empty.pdf")

    assert result["text"] == ""
    assert isinstance(result["fk_grade"], float)
