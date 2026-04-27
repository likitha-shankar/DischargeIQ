"""
File: dischargeiq/tests/test_recovery_agent.py
Owner: Likitha Shankar
Description: Black-box tests for Agent 4 (run_recovery_agent).  Mocks the
  Anthropic client at the agent's _get_client target so tests are deterministic
  and offline.  Verifies happy path, minimal-extraction handling, and the
  Bug C empty-content guard.
Key functions/classes: test_* functions, _fake_client(), _surgical_extraction()
Edge cases handled:
  - Empty Anthropic content → empty string (not IndexError) per Bug C fix.
  - Minimal extraction with only primary_diagnosis → still produces text.
Dependencies: pytest, unittest.mock, dischargeiq.agents.recovery_agent
Called by: pytest (testpaths = dischargeiq/tests per pytest.ini).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from dischargeiq.agents import recovery_agent
from dischargeiq.models.extraction import (
    ExtractionOutput, Medication, FollowUpAppointment,
)

_MOCK_CLIENT_TARGET = "dischargeiq.agents.recovery_agent._get_client"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _fake_client(reply_text: str) -> MagicMock:
    """MagicMock client whose .messages.create returns a fake Anthropic response."""
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text=reply_text)]
    )
    return client


def _surgical_extraction() -> ExtractionOutput:
    """Post-cholecystectomy ExtractionOutput for happy-path tests."""
    return ExtractionOutput(
        primary_diagnosis="Acute calculous cholecystitis — laparoscopic cholecystectomy",
        medications=[
            Medication(name="Oxycodone/Acetaminophen", dose="5/325mg", frequency="every 6h prn"),
            Medication(name="Docusate Sodium", dose="100mg", frequency="twice daily"),
        ],
        follow_up_appointments=[
            FollowUpAppointment(provider="General Surgery", date="2026-05-04"),
        ],
        activity_restrictions=["no lifting > 10 lbs for 2 weeks"],
        red_flag_symptoms=["fever > 101F", "wound drainage"],
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_happy_path_returns_recovery_text():
    """Surgical extraction → returns recovery text + fk grade + passes."""
    extraction = _surgical_extraction()
    reply = (
        "Week 1: Rest at home. No lifting more than 10 pounds. "
        "Walk a little each day to keep your blood moving.\n\n"
        "Week 2: You can do light chores. Keep the wound dry. "
        "See your surgeon at the follow-up visit."
    )
    with patch(_MOCK_CLIENT_TARGET, return_value=_fake_client(reply)):
        result = recovery_agent.run_recovery_agent(extraction, document_id="surg_01.pdf")

    assert isinstance(result, dict)
    assert set(result) >= {"text", "fk_grade", "passes"}
    assert "Week" in result["text"]
    assert isinstance(result["fk_grade"], float)


def test_minimal_extraction_only_diagnosis_works():
    """
    Only primary_diagnosis present → still produces a valid recovery timeline.
    No medications, no follow-ups, no restrictions.
    """
    extraction = ExtractionOutput(primary_diagnosis="Minor concussion")
    reply = (
        "Week 1: Rest your brain. Limit screen time. "
        "Drink plenty of water. Most people feel better in a few days."
    )
    with patch(_MOCK_CLIENT_TARGET, return_value=_fake_client(reply)):
        result = recovery_agent.run_recovery_agent(extraction, document_id="concussion.pdf")

    assert result["text"] != ""
    assert isinstance(result["fk_grade"], float)


def test_empty_anthropic_content_returns_empty_text_no_crash():
    """
    Bug C regression: Anthropic returns content=[] → empty string output, no
    IndexError.  The guard at recovery_agent.py:297 preserves the contract.
    """
    extraction = _surgical_extraction()
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(content=[])
    with patch(_MOCK_CLIENT_TARGET, return_value=client):
        result = recovery_agent.run_recovery_agent(extraction, document_id="empty.pdf")

    assert result["text"] == ""
    assert isinstance(result["fk_grade"], float)
