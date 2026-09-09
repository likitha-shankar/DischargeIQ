"""
What is allowed to reach the database.

CLAUDE.md: "Never store full PDF text or free-text agent outputs in the
database. Only store structured fields, hashes, and metadata."

The insert wrote `extraction.model_dump()` whole. That satisfies "structured
fields" on a literal reading and defeats the intent, because two of those
fields are not the kind of structure the rule means:

  patient_name        a direct identifier, one of the eighteen under HIPAA
  *_source spans      VERBATIM text lifted from the document - 272 of them
                      across the 106-document corpus - which can carry
                      anything the hospital wrote: names, dates of birth,
                      record numbers, addresses

It was invisible because the corpus is de-identified: MTSamples scrubs names,
so `patient_name` extracts as "female" or "The patient" and looks harmless.
On real paperwork it is a real name, and the store becomes a HIPAA record
with no retention policy and no deletion path.

These tests are written against the property, not the implementation: no
matter what Agent 1 returns, an identifier and a verbatim span must not reach
storage.
"""

import json

import pytest

from dischargeiq.db.history import redact_for_storage
from dischargeiq.models.extraction import (
    ExtractionOutput,
    FollowUpAppointment,
    Medication,
    SourceSpan,
)


def _full_extraction() -> ExtractionOutput:
    """An extraction with every identifier-bearing field populated."""
    return ExtractionOutput(
        patient_name="Jane Q Patient",
        patient_name_source=SourceSpan(
            page=1, text="Patient: Jane Q Patient, DOB 01/02/1950, MRN 8823419"),
        discharge_date="2026-08-22",
        discharge_date_source=SourceSpan(page=1, text="Discharged 08/22/2026"),
        primary_diagnosis="Acute decompensated heart failure",
        primary_diagnosis_source=SourceSpan(
            page=2, text="Ms Patient was admitted with heart failure"),
        secondary_diagnoses=["Hypertension"],
        medications=[Medication(name="Furosemide", dose="40 mg")],
        follow_up_appointments=[FollowUpAppointment(provider="Dr Chen")],
        red_flag_symptoms=["Weight gain of 3 pounds in one day"],
    )


class TestIdentifiersNeverReachStorage:
    """The property, stated as a property."""

    def test_the_patient_name_is_not_persisted(self):
        stored = redact_for_storage(_full_extraction())
        assert "patient_name" not in stored

    def test_no_source_span_is_persisted(self):
        stored = redact_for_storage(_full_extraction())
        assert not [k for k in stored if k.endswith("_source")]

    def test_the_name_does_not_survive_anywhere_in_the_json(self):
        """
        Key-by-key checks miss a value that leaks through another field. This
        checks the serialised blob that actually goes into the column.
        """
        blob = json.dumps(redact_for_storage(_full_extraction()))
        assert "Jane Q Patient" not in blob

    def test_verbatim_document_text_does_not_survive_in_the_json(self):
        """The spans are where a date of birth or a record number would ride."""
        blob = json.dumps(redact_for_storage(_full_extraction()))
        for leaked in ("DOB 01/02/1950", "MRN 8823419", "Ms Patient was admitted"):
            assert leaked not in blob, leaked


class TestClinicalStructureIsKept:
    """
    The half that decides whether this is usable. Redaction that removed the
    clinical content would leave the history screen and the clinician
    dashboard with nothing to show.
    """

    def test_the_diagnosis_is_kept(self):
        stored = redact_for_storage(_full_extraction())
        assert stored["primary_diagnosis"] == "Acute decompensated heart failure"
        assert stored["secondary_diagnoses"] == ["Hypertension"]

    def test_medications_are_kept(self):
        stored = redact_for_storage(_full_extraction())
        assert stored["medications"][0]["name"] == "Furosemide"
        assert stored["medications"][0]["dose"] == "40 mg"

    def test_appointments_and_warning_signs_are_kept(self):
        stored = redact_for_storage(_full_extraction())
        assert stored["follow_up_appointments"][0]["provider"] == "Dr Chen"
        assert stored["red_flag_symptoms"] == ["Weight gain of 3 pounds in one day"]

    def test_the_discharge_date_is_kept(self):
        """
        A date of service is not one of the fields dropped here. It is a
        column in its own right, the history screen orders by it, and the
        recovery timeline is measured from it.
        """
        assert redact_for_storage(_full_extraction())["discharge_date"] == "2026-08-22"


class TestEdgeCases:
    def test_an_empty_extraction_redacts_without_error(self):
        stored = redact_for_storage(ExtractionOutput(primary_diagnosis="X"))
        assert stored["primary_diagnosis"] == "X"
        assert "patient_name" not in stored

    def test_redaction_does_not_mutate_the_original(self):
        """
        The live API response still carries names and spans - the app draws
        citation chips from them. Redaction is for STORAGE only, and must not
        reach back into the object the response is built from.
        """
        extraction = _full_extraction()
        redact_for_storage(extraction)
        assert extraction.patient_name == "Jane Q Patient"
        assert extraction.patient_name_source is not None

    @pytest.mark.parametrize("name", ["", "   ", None])
    def test_an_absent_name_is_handled(self, name):
        extraction = ExtractionOutput(primary_diagnosis="X", patient_name=name)
        assert "patient_name" not in redact_for_storage(extraction)
