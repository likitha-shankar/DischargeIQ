"""
File: dischargeiq/tests/test_agent6_simulator.py
Owner: Likitha Shankar
Description: Black-box unit tests for Agent 6 (patient_simulator_agent).
  All LLM calls are mocked — no network I/O, no API keys required.
  Covers happy path, critical gap detection, well-written doc scoring,
  empty pipeline input, malformed LLM output, and missing SEVERITY field.
Key functions/classes: test_* functions, _minimal_extraction(), _make_llm_response()
Edge cases handled:
  - Malformed LLM response must not raise; fallback PatientSimulatorOutput returned.
  - Missing SEVERITY lines must default to "moderate" without KeyError.
  - Empty ExtractionOutput (primary_diagnosis="Unknown") must not raise.
Dependencies: pytest, unittest.mock, dischargeiq.agents.patient_simulator_agent,
  dischargeiq.models.extraction, dischargeiq.models.pipeline
Called by: pytest (testpaths = dischargeiq/tests per pytest.ini).
"""

import logging
from unittest.mock import patch

import pytest

from dischargeiq.agents.patient_simulator_agent import run_patient_simulator_agent
from dischargeiq.models.extraction import ExtractionOutput, FollowUpAppointment, Medication
from dischargeiq.models.pipeline import PatientSimulatorOutput

# ── Mock targets ───────────────────────────────────────────────────────────────
# Patch names as imported in the agent module, not their origin modules.
# get_llm_client() performs the API key check before call_chat_with_fallback runs,
# so both must be mocked to avoid requiring real credentials in unit tests.
_MOCK_CHAT = "dischargeiq.agents.patient_simulator_agent.call_chat_with_fallback"
_MOCK_CLIENT = "dischargeiq.agents.patient_simulator_agent.get_llm_client"

# Fake (client, model_name) pair returned by the mocked get_llm_client.
_FAKE_CLIENT_PAIR = (object(), "fake-model")

# ── Helpers ────────────────────────────────────────────────────────────────────

_VALID_SEVERITIES = {"critical", "moderate", "minor"}


def _minimal_extraction() -> ExtractionOutput:
    """Return a realistic ExtractionOutput for use as the primary test input."""
    return ExtractionOutput(
        primary_diagnosis="Type 2 Diabetes",
        medications=[
            Medication(name="Metformin", dose="500mg", frequency="twice daily")
        ],
        follow_up_appointments=[
            FollowUpAppointment(provider="Dr. Smith", date="2026-05-01")
        ],
        red_flag_symptoms=["chest pain", "shortness of breath"],
        activity_restrictions=["no heavy lifting"],
        dietary_restrictions=["low sugar diet"],
    )


def _make_llm_response(blocks: list[dict], gap_score: int = 6, summary: str = "") -> str:
    """
    Build a well-formed Agent 6 text response from a list of question dicts.

    Each dict may contain: question (str), answered (str "YES"/"NO"),
    gap (str), severity (str). All keys are optional — omitting severity tests
    the default-fallback path.
    """
    lines: list[str] = []
    for b in blocks:
        lines.append(f"Q: {b.get('question', 'What should I do?')}")
        if "answered" in b:
            lines.append(f"ANSWERED: {b['answered']}")
        if "gap" in b:
            lines.append(f"GAP: {b['gap']}")
        if "severity" in b:
            lines.append(f"SEVERITY: {b['severity']}")
        lines.append("")
    lines.append(f"OVERALL_GAP_SCORE: {gap_score}")
    lines.append(f"SUMMARY: {summary or 'Patients with limited literacy will struggle most.'}")
    return "\n".join(lines)


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_happy_path_returns_valid_output():
    """Well-formed 6-question response → valid PatientSimulatorOutput."""
    blocks = [
        {
            "question": "What happens if I forget to take my Metformin?",
            "answered": "NO",
            "gap": "No instructions for missed doses.",
            "severity": "critical",
        },
        {
            "question": "Can I eat sweets once in a while?",
            "answered": "NO",
            "gap": "Dietary guidance is too vague.",
            "severity": "moderate",
        },
        {
            "question": "Should I check my blood sugar at home?",
            "answered": "YES",
            "gap": "N/A",
            "severity": "minor",
        },
        {
            "question": "What does twice daily mean — morning and night?",
            "answered": "NO",
            "gap": "Timing not specified.",
            "severity": "moderate",
        },
        {
            "question": "Is it okay to drink alcohol?",
            "answered": "NO",
            "gap": "Alcohol interaction not mentioned.",
            "severity": "moderate",
        },
        {
            "question": "When exactly is my follow-up with Dr. Smith?",
            "answered": "YES",
            "gap": "N/A",
            "severity": "minor",
        },
    ]
    raw = _make_llm_response(blocks, gap_score=7, summary="Patients unfamiliar with diabetes management will struggle.")

    with patch(_MOCK_CLIENT, return_value=_FAKE_CLIENT_PAIR), \
         patch(_MOCK_CHAT, return_value=raw):
        result = run_patient_simulator_agent(_minimal_extraction(), "test_happy")

    assert isinstance(result, PatientSimulatorOutput)
    assert 0 <= result.overall_gap_score <= 10
    assert result.simulator_summary != ""
    assert len(result.missed_concepts) >= 1
    for concept in result.missed_concepts:
        assert hasattr(concept, "question")
        assert hasattr(concept, "answered_by_doc")
        assert hasattr(concept, "gap_summary")
        assert hasattr(concept, "severity")
        assert concept.severity in _VALID_SEVERITIES


def test_obvious_gaps_produce_critical_unanswered_concept():
    """Response with missing follow-up/diet/meds info → ≥1 critical unanswered concept."""
    blocks = [
        {
            "question": "Nobody told me when to see my doctor again — is that normal?",
            "answered": "NO",
            "gap": "Follow-up timing is not specified in the document.",
            "severity": "critical",
        },
        {
            "question": "What foods should I avoid with my diabetes?",
            "answered": "NO",
            "gap": "Dietary restrictions are absent.",
            "severity": "critical",
        },
        {
            "question": "How long do I take Metformin?",
            "answered": "NO",
            "gap": "Medication duration is not stated.",
            "severity": "critical",
        },
    ]
    raw = _make_llm_response(blocks, gap_score=9)

    with patch(_MOCK_CLIENT, return_value=_FAKE_CLIENT_PAIR), \
         patch(_MOCK_CHAT, return_value=raw):
        result = run_patient_simulator_agent(_minimal_extraction(), "test_gaps")

    assert any(
        c.severity == "critical" and not c.answered_by_doc
        for c in result.missed_concepts
    ), "Expected at least one critical unanswered concept"


def test_well_written_doc_produces_low_gap_score():
    """All questions answered → gap score ≤ 4 and majority of concepts answered_by_doc."""
    blocks = [
        {
            "question": "What is Metformin for?",
            "answered": "YES",
            "gap": "N/A",
            "severity": "minor",
        },
        {
            "question": "When is my follow-up?",
            "answered": "YES",
            "gap": "N/A",
            "severity": "minor",
        },
        {
            "question": "What foods should I avoid?",
            "answered": "YES",
            "gap": "N/A",
            "severity": "minor",
        },
        {
            "question": "What are the warning signs I need to watch for?",
            "answered": "YES",
            "gap": "N/A",
            "severity": "minor",
        },
        {
            "question": "Can I do light exercise?",
            "answered": "YES",
            "gap": "N/A",
            "severity": "minor",
        },
        {
            "question": "How do I take my medication?",
            "answered": "YES",
            "gap": "N/A",
            "severity": "minor",
        },
    ]
    raw = _make_llm_response(blocks, gap_score=2, summary="This document is clear and complete.")

    with patch(_MOCK_CLIENT, return_value=_FAKE_CLIENT_PAIR), \
         patch(_MOCK_CHAT, return_value=raw):
        result = run_patient_simulator_agent(_minimal_extraction(), "test_well_written")

    assert result.overall_gap_score <= 4
    answered_count = sum(1 for c in result.missed_concepts if c.answered_by_doc)
    assert answered_count >= len(result.missed_concepts) // 2, (
        f"Expected most concepts answered, got {answered_count}/{len(result.missed_concepts)}"
    )


def test_empty_pipeline_result_does_not_raise():
    """Minimal ExtractionOutput (primary_diagnosis only) must not raise."""
    empty_extraction = ExtractionOutput(primary_diagnosis="Unknown")
    blocks = [
        {
            "question": "What was wrong with me?",
            "answered": "NO",
            "gap": "Diagnosis not explained.",
            "severity": "moderate",
        },
        {
            "question": "What should I do when I get home?",
            "answered": "NO",
            "gap": "No discharge instructions provided.",
            "severity": "moderate",
        },
    ]
    raw = _make_llm_response(blocks, gap_score=5)

    with patch(_MOCK_CLIENT, return_value=_FAKE_CLIENT_PAIR), \
         patch(_MOCK_CHAT, return_value=raw):
        result = run_patient_simulator_agent(empty_extraction, "test_empty")

    assert isinstance(result, PatientSimulatorOutput)


def test_malformed_llm_response_returns_fallback_no_raise(caplog):
    """Completely malformed LLM response → no exception, fallback output, WARNING logged."""
    malformed = "INVALID OUTPUT — not a valid Q block or JSON"

    with patch(_MOCK_CLIENT, return_value=_FAKE_CLIENT_PAIR), \
         patch(_MOCK_CHAT, return_value=malformed):
        with caplog.at_level(logging.WARNING, logger="dischargeiq.agents.patient_simulator_agent"):
            result = run_patient_simulator_agent(_minimal_extraction(), "test_malformed")

    assert isinstance(result, PatientSimulatorOutput)
    assert result.overall_gap_score == 0
    assert result.missed_concepts == []

    warning_text = caplog.text.lower()
    assert "agent6" in warning_text or "parse" in warning_text, (
        f"Expected a WARNING log containing 'agent6' or 'parse', got: {caplog.text!r}"
    )


def test_missing_severity_defaults_to_moderate():
    """Q blocks with no SEVERITY line must default to 'moderate' — no KeyError."""
    blocks = [
        {
            "question": "What is this medication supposed to do for me?",
            "answered": "NO",
            "gap": "No rationale given for Metformin.",
            # severity intentionally omitted
        },
        {
            "question": "How do I know if something is wrong?",
            "answered": "NO",
            "gap": "Red flag symptoms not listed.",
            # severity intentionally omitted
        },
        {
            "question": "When should I call the doctor?",
            "answered": "NO",
            "gap": "No guidance on when to seek help.",
            # severity intentionally omitted
        },
    ]
    raw = _make_llm_response(blocks, gap_score=6)

    with patch(_MOCK_CLIENT, return_value=_FAKE_CLIENT_PAIR), \
         patch(_MOCK_CHAT, return_value=raw):
        result = run_patient_simulator_agent(_minimal_extraction(), "test_no_severity")

    assert isinstance(result, PatientSimulatorOutput)
    for concept in result.missed_concepts:
        assert concept.severity == "moderate", (
            f"Expected 'moderate' default, got '{concept.severity}' for: {concept.question!r}"
        )
