"""
Tests for the FHIR R4 -> ExtractionOutput adapter (Liebovitz review item 3.4).

A FHIR bundle lets the pipeline skip Agent 1 entirely: dose, date and provider
arrive as typed values, so extraction error for those fields does not get
smaller, it disappears. That makes the adapter itself the new single point of
failure, and these tests are weighted accordingly.

The two that matter most:

  test_stopped_medication_is_excluded - a discontinued drug appearing on a
  discharge list is how a patient keeps taking something they were told to
  stop. This is the only test here where a bug is directly dangerous.

  test_fhir_cannot_supply_warning_signs - FHIR carries no red flags, activity
  or dietary restrictions. If that ever silently starts returning content, the
  escalation guide is being fed something FHIR does not actually know.
"""

import pytest

from dischargeiq.utils.fhir_adapter import extraction_from_bundle


def _bundle(*resources) -> dict:
    """Wrap resources in a Bundle."""
    return {"resourceType": "Bundle",
            "entry": [{"resource": r} for r in resources]}


def _condition(cid="c1", text="Pneumonia") -> dict:
    return {"resourceType": "Condition", "id": cid, "code": {"text": text}}


def _med(mid="m1", name="Furosemide", status="active", value=40, unit="mg",
         text="once daily") -> dict:
    return {
        "resourceType": "MedicationRequest", "id": mid, "status": status,
        "medicationCodeableConcept": {"text": name},
        "dosageInstruction": [{
            "text": text,
            "doseAndRate": [{"doseQuantity": {"value": value, "unit": unit}}],
        }],
    }


class TestMedicationSafety:
    """The only place in this file where a bug hurts a patient directly."""

    def test_stopped_medication_is_excluded(self):
        """
        A drug the clinician stopped must never reach the patient's list.

        FHIR marks this explicitly, which is exactly the advantage over
        reading a PDF - but only if the status is actually honoured.
        """
        ex, _ = extraction_from_bundle(_bundle(
            _condition(),
            _med("m1", "Furosemide", status="active"),
            _med("m2", "Warfarin", status="stopped"),
            _med("m3", "Digoxin", status="cancelled"),
            _med("m4", "Amiodarone", status="entered-in-error"),
        ))
        names = {m.name for m in ex.medications}
        assert names == {"Furosemide"}

    def test_active_and_completed_are_kept(self):
        ex, _ = extraction_from_bundle(_bundle(
            _condition(),
            _med("m1", "Aspirin", status="active"),
            _med("m2", "Amoxicillin", status="completed"),
        ))
        assert {m.name for m in ex.medications} == {"Aspirin", "Amoxicillin"}

    def test_a_medication_with_no_usable_name_is_dropped_not_guessed(self):
        """
        medicationReference points at a Medication resource that may not be in
        the bundle. Recording a dose with no drug name attached is worse than
        recording nothing: it looks like an instruction and names nothing.
        """
        ex, _ = extraction_from_bundle(_bundle(
            _condition(),
            {"resourceType": "MedicationRequest", "id": "m9", "status": "active",
             "medicationReference": {"reference": "Medication/x"},
             "dosageInstruction": [{"text": "twice daily"}]},
        ))
        assert ex.medications == []

    def test_dose_renders_for_a_patient_not_a_machine(self):
        """40.0 mg is a float leaking into a patient's medication list."""
        ex, _ = extraction_from_bundle(_bundle(_condition(), _med(value=40.0)))
        assert ex.medications[0].dose == "40 mg"

    def test_fractional_dose_is_preserved(self):
        ex, _ = extraction_from_bundle(_bundle(_condition(), _med(value=3.125)))
        assert ex.medications[0].dose == "3.125 mg"


class TestPrimaryDiagnosis:
    """Which condition is principal is a clinical judgement, not a position."""

    def test_encounter_rank_decides_the_primary(self):
        ex, _ = extraction_from_bundle(_bundle(
            _condition("c1", "Hypertension"),
            _condition("c2", "Acute Heart Failure"),
            {"resourceType": "Encounter", "id": "e1",
             "diagnosis": [{"condition": {"reference": "Condition/c2"}, "rank": 1}]},
        ))
        # c1 comes first in the bundle; the rank must win.
        assert ex.primary_diagnosis == "Acute Heart Failure"
        assert ex.secondary_diagnoses == ["Hypertension"]

    def test_without_a_rank_the_guess_is_declared(self):
        """
        Falling back to the first Condition is defensible. Doing it silently
        is not - the caller needs to know the primary may be wrong.
        """
        ex, _ = extraction_from_bundle(_bundle(
            _condition("c1", "Hypertension"), _condition("c2", "Pneumonia"),
        ))
        assert ex.primary_diagnosis == "Hypertension"
        assert any("rank" in w for w in ex.extraction_warnings)

    def test_no_condition_fails_loudly(self):
        """
        Every downstream agent requires a primary diagnosis. A bundle without
        one is not a discharge summary, and emitting a record that explains
        nothing would be worse than refusing it.
        """
        with pytest.raises(ValueError, match="primary diagnosis"):
            extraction_from_bundle(_bundle(_med()))

    def test_coded_concept_prefers_display_over_raw_code(self):
        """A patient reading "I50.9" has been given nothing."""
        ex, _ = extraction_from_bundle(_bundle({
            "resourceType": "Condition", "id": "c1",
            "code": {"coding": [{"code": "I50.9", "display": "Heart failure"}]},
        }))
        assert ex.primary_diagnosis == "Heart failure"

    def test_a_bare_code_is_used_only_as_a_last_resort(self):
        ex, _ = extraction_from_bundle(_bundle({
            "resourceType": "Condition", "id": "c1",
            "code": {"coding": [{"code": "I50.9"}]},
        }))
        assert ex.primary_diagnosis == "I50.9"


class TestWhatFhirCannotDo:
    """The finding that decides whether 'prefer FHIR' is worth the build."""

    def test_fhir_cannot_supply_warning_signs(self):
        """
        No discrete FHIR resource carries red flags, activity or dietary
        restrictions - they live in narrative discharge instructions. So a
        FHIR-sourced record leaves Agent 5, the highest-risk output in the
        product, with no input at all.

        These must stay empty. Content appearing here would mean something is
        inventing what FHIR does not know.
        """
        ex, coverage = extraction_from_bundle(_bundle(
            _condition(), _med(),
            {"resourceType": "Appointment", "id": "a1", "start": "2026-04-05"},
        ))
        assert ex.red_flag_symptoms == []
        assert ex.activity_restrictions == []
        assert ex.dietary_restrictions == []
        assert coverage.needs_narrative is True
        assert "red_flag_symptoms" in coverage.fields_unavailable

    def test_the_limitation_is_stated_in_the_record_itself(self):
        """A reader of the extraction alone must see the gap."""
        ex, _ = extraction_from_bundle(_bundle(_condition(), _med()))
        assert any("warning signs" in w.lower() for w in ex.extraction_warnings)


class TestProvenance:
    """Citation chips are the trust mechanism; they must not lie."""

    def test_source_names_the_resource_not_a_fake_page(self):
        """
        SourceSpan carries a page number because it was built for PDFs. A FHIR
        value has no page, so page 0 means "not from a document" and the text
        names the resource. Inventing page 1 would make a citation point at
        something that does not exist.
        """
        ex, _ = extraction_from_bundle(_bundle(_condition(), _med("m7")))
        source = ex.medications[0].source
        assert source.page == 0
        assert "MedicationRequest/m7" in source.text


class TestMalformedInput:
    """A bad bundle falls back to the PDF path; it must not crash."""

    @pytest.mark.parametrize("bundle", [
        {}, {"resourceType": "Bundle"}, {"entry": None},
        {"entry": [None]}, {"entry": [{"resource": None}]},
    ])
    def test_missing_or_broken_structure_raises_only_the_expected_error(self, bundle):
        with pytest.raises(ValueError):
            extraction_from_bundle(bundle)

    def test_appointment_without_participants_still_maps(self):
        ex, _ = extraction_from_bundle(_bundle(
            _condition(),
            {"resourceType": "Appointment", "id": "a1",
             "start": "2026-04-05T09:00:00Z"},
        ))
        appt = ex.follow_up_appointments[0]
        assert appt.date == "2026-04-05"   # date only, not an instant
        assert appt.provider is None       # absent, not invented
