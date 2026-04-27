"""
File: dischargeiq/tests/test_escalation_agent.py
Owner: Likitha Shankar
Description: Black-box tests for Agent 5 (run_escalation_agent) — the
  safety-critical three-tier warning-sign decision tree.  Mocks the Anthropic
  client at the agent's _get_client target so tests are deterministic and
  offline.  Verifies the LOCKED rules from CLAUDE.md: red-flag symptoms are
  preserved verbatim, 911 language survives, and empty inputs degrade safely.
Key functions/classes: test_* functions, _fake_client(), _hf_extraction()
Edge cases handled:
  - Heart-failure red flags must survive in output (no fabrication).
  - Empty red_flag_symptoms → safe minimal output, never invent symptoms.
  - Empty Anthropic content → empty string per Bug C guard.
Dependencies: pytest, unittest.mock, dischargeiq.agents.escalation_agent
Called by: pytest (testpaths = dischargeiq/tests per pytest.ini).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from dischargeiq.agents import escalation_agent
from dischargeiq.models.extraction import ExtractionOutput

_MOCK_CLIENT_TARGET = "dischargeiq.agents.escalation_agent._get_client"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _fake_client(reply_text: str) -> MagicMock:
    """MagicMock client whose .messages.create returns a fake Anthropic response."""
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(text=reply_text)]
    )
    return client


def _hf_extraction() -> ExtractionOutput:
    """Heart-failure ExtractionOutput with explicit red flag symptoms."""
    return ExtractionOutput(
        primary_diagnosis="Acute Decompensated Heart Failure",
        red_flag_symptoms=[
            "chest pain",
            "shortness of breath at rest",
            "weight gain of 3+ pounds in 2 days",
        ],
    )


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_happy_path_preserves_red_flag_language():
    """
    Heart-failure extraction → output must include the red-flag symptoms
    verbatim and contain explicit 911 language.  Agent 5 is safety-critical;
    it must never paraphrase warning signs into softer language.
    """
    extraction = _hf_extraction()
    reply = (
        "Call 911 now if you have chest pain or shortness of breath at rest. "
        "These can mean another heart attack.\n\n"
        "Call your doctor today if you gain 3 or more pounds in 2 days. "
        "This means fluid is building up.\n\n"
        "Watch for: ankle swelling, tiredness. Tell your doctor at your "
        "next visit."
    )
    with patch(_MOCK_CLIENT_TARGET, return_value=_fake_client(reply)):
        result = escalation_agent.run_escalation_agent(extraction, document_id="hf_01.pdf")

    assert isinstance(result, dict)
    assert set(result) >= {"text", "fk_grade", "passes"}
    assert "911" in result["text"], "Heart-failure escalation must contain 911 trigger"
    assert "chest pain" in result["text"]
    assert "shortness of breath" in result["text"]


def test_empty_red_flags_does_not_crash():
    """
    Extraction with no red_flag_symptoms → agent still runs, produces output
    (may be a generic safe fallback).  Per CLAUDE.md hard rule #1, the agent
    must NEVER fabricate symptoms it didn't see.
    """
    extraction = ExtractionOutput(
        primary_diagnosis="Mild post-op pain",
        red_flag_symptoms=[],
    )
    safe_reply = (
        "If you feel something is wrong, call your doctor. "
        "If you cannot reach your doctor and feel unsafe, go to the nearest ER."
    )
    with patch(_MOCK_CLIENT_TARGET, return_value=_fake_client(safe_reply)):
        result = escalation_agent.run_escalation_agent(extraction, document_id="postop.pdf")

    assert result["text"] != ""
    assert isinstance(result["fk_grade"], float)


def test_call_911_language_present_when_red_flag_critical():
    """When the LLM emits 911 language for critical red flags, it survives the FK pipeline."""
    extraction = _hf_extraction()
    reply = "Call 911 right away if you have chest pain. This is an emergency."
    with patch(_MOCK_CLIENT_TARGET, return_value=_fake_client(reply)):
        result = escalation_agent.run_escalation_agent(extraction, document_id="hf_911.pdf")

    assert "911" in result["text"]
    assert "Call 911" in result["text"] or "call 911" in result["text"]


def test_empty_anthropic_content_returns_empty_text_no_crash():
    """
    Bug C regression: Anthropic returns content=[] → empty string, no IndexError.
    Critical for safety-sensitive Agent 5 — a crash here would void the
    pipeline, while the guard lets the orchestrator mark partial.
    """
    extraction = _hf_extraction()
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(content=[])
    with patch(_MOCK_CLIENT_TARGET, return_value=client):
        result = escalation_agent.run_escalation_agent(extraction, document_id="empty.pdf")

    assert result["text"] == ""
    assert isinstance(result["fk_grade"], float)
