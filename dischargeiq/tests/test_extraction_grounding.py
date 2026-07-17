"""
Unit tests for the deterministic grounding check in Agent 1
(dischargeiq/agents/extraction_agent.py::_check_grounding).

The check is the runtime hallucination guard: any extracted medication or
follow-up provider name with zero textual support in the source document
must produce a patient-facing verify warning, and grounded values must
produce none. Pure function, no LLM calls, no network.

Run with:
    python -m pytest dischargeiq/tests/test_extraction_grounding.py -q
"""

from dischargeiq.agents.extraction_agent import _check_grounding
from dischargeiq.models.extraction import (
    ExtractionOutput,
    FollowUpAppointment,
    Medication,
)

_SOURCE = (
    "DISCHARGE SUMMARY\n"
    "Medications: Albuterol (ProAir HFA) 90mcg 2 puffs every 4-6 hours.\n"
    "Prednisone 40mg daily for 5 days.\n"
    "Follow up with Dr. Sarah Chen, Pulmonology, on 2026-03-24.\n"
)


def _output(meds: list[Medication], appts: list[FollowUpAppointment]) -> ExtractionOutput:
    return ExtractionOutput(
        primary_diagnosis="COPD exacerbation",
        medications=meds,
        follow_up_appointments=appts,
    )


def test_grounded_values_produce_no_warnings() -> None:
    result = _output(
        [Medication(name="Albuterol (ProAir HFA)"), Medication(name="Prednisone")],
        [FollowUpAppointment(provider="Dr. Sarah Chen")],
    )
    assert _check_grounding(_SOURCE, result) == []


def test_fabricated_medication_is_flagged() -> None:
    result = _output([Medication(name="Metformin")], [])
    warnings = _check_grounding(_SOURCE, result)
    assert len(warnings) == 1
    assert "Metformin" in warnings[0]
    assert "verify" in warnings[0]


def test_fabricated_provider_is_flagged() -> None:
    result = _output([], [FollowUpAppointment(provider="Dr. James Rodriguez")])
    warnings = _check_grounding(_SOURCE, result)
    assert len(warnings) == 1
    assert "James Rodriguez" in warnings[0]


def test_partial_token_match_counts_as_grounded() -> None:
    # One matching 4+ char token clears the value: "ProAir" appears in the
    # source even though the LLM dropped the "Albuterol" half of the name.
    result = _output([Medication(name="ProAir inhaler")], [])
    assert _check_grounding(_SOURCE, result) == []


def test_short_or_empty_names_are_skipped() -> None:
    # No 4+ char alphabetic token -> not checkable -> no warning.
    result = _output([Medication(name="B12")], [FollowUpAppointment(provider=None)])
    assert _check_grounding(_SOURCE, result) == []


def test_case_insensitive_matching() -> None:
    result = _output([Medication(name="PREDNISONE")], [])
    assert _check_grounding(_SOURCE, result) == []
