"""
Unit tests for the deterministic grounding check in Agent 1
(dischargeiq/agents/extraction_agent.py::_check_grounding).

The check is the runtime hallucination guard: any extracted verbatim-contract
field (patient name, diagnoses, procedures, medication names and dose
numbers, providers, specialties, restrictions, red flags, condition) with
zero textual support in the source document must produce a patient-facing
verify warning, and grounded values must produce none. Pure function, no
LLM calls, no network.

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
    "Diagnosis: COPD exacerbation.\n"
    "Medications: Albuterol (ProAir HFA) 90mcg 2 puffs every 4-6 hours.\n"
    "Prednisone 40mg daily for 5 days.\n"
    "Follow up with Dr. Sarah Chen, Pulmonology, on 2026-03-24.\n"
    "Avoid heavy lifting. Call if fever or worsening shortness of breath.\n"
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


def test_generic_words_do_not_clear_fabricated_medication() -> None:
    # "take" and "daily" appear in most documents; they must not ground a
    # fabricated drug name on their own.
    result = _output([Medication(name="Take Metformin daily")], [])
    warnings = _check_grounding(_SOURCE, result)
    assert len(warnings) == 1
    assert "Metformin" in warnings[0]


def test_fabricated_dose_number_is_flagged() -> None:
    # Prednisone is real but the document says 40mg, not 80mg.
    result = _output([Medication(name="Prednisone", dose="80mg")], [])
    warnings = _check_grounding(_SOURCE, result)
    assert len(warnings) == 1
    assert "80mg" in warnings[0]
    assert "Prednisone" in warnings[0]


def test_grounded_dose_number_passes() -> None:
    # "40" appears in "40mg"; must not match inside "2026" style years either.
    result = _output([Medication(name="Prednisone", dose="40 mg")], [])
    assert _check_grounding(_SOURCE, result) == []


def test_dose_number_does_not_match_inside_larger_number() -> None:
    # Source has 2026 and 40; a fabricated "20" must not clear via "2026".
    result = _output([Medication(name="Prednisone", dose="20mg")], [])
    warnings = _check_grounding(_SOURCE, result)
    assert len(warnings) == 1
    assert "20mg" in warnings[0]


def test_fabricated_diagnosis_is_flagged() -> None:
    result = ExtractionOutput(
        primary_diagnosis="Congestive heart failure",
        secondary_diagnoses=["Atrial fibrillation"],
    )
    warnings = _check_grounding(_SOURCE, result)
    assert len(warnings) == 2
    assert any("heart failure" in w for w in warnings)
    assert any("Atrial fibrillation" in w for w in warnings)


def test_fabricated_specialty_and_grounded_provider() -> None:
    result = _output(
        [], [FollowUpAppointment(provider="Dr. Sarah Chen", specialty="Cardiology")]
    )
    warnings = _check_grounding(_SOURCE, result)
    assert len(warnings) == 1
    assert "Cardiology" in warnings[0]


def test_grounded_restrictions_and_red_flags_pass() -> None:
    result = ExtractionOutput(
        primary_diagnosis="COPD exacerbation",
        activity_restrictions=["Avoid heavy lifting"],
        red_flag_symptoms=["Fever", "Worsening shortness of breath"],
        discharge_condition=None,
    )
    assert _check_grounding(_SOURCE, result) == []


def test_fabricated_red_flag_is_flagged() -> None:
    result = ExtractionOutput(
        primary_diagnosis="COPD exacerbation",
        red_flag_symptoms=["Sudden vision changes"],
    )
    warnings = _check_grounding(_SOURCE, result)
    assert len(warnings) == 1
    assert "Sudden vision changes" in warnings[0]
