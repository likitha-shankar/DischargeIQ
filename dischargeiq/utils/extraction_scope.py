"""
Narrow copies of ExtractionOutput for Agents 2–5.

Each downstream agent only needs a subset of fields in its user message.
Passing a scoped model reduces prompt tokens and limits cross-field confusion.

Depends on: dischargeiq.models.extraction.ExtractionOutput.
"""

from dischargeiq.models.extraction import ExtractionOutput


def scope_for_agent2(extraction: ExtractionOutput) -> ExtractionOutput:
    """Primary + secondary diagnoses only (no procedures — orchestrator clears those)."""
    return extraction.model_copy(
        update={
            "patient_name": None,
            "discharge_date": None,
            "primary_diagnosis_source": None,
            "procedures_performed": [],
            "medications": [],
            "follow_up_appointments": [],
            "activity_restrictions": [],
            "dietary_restrictions": [],
            "red_flag_symptoms": [],
            "discharge_condition": None,
            "extraction_warnings": [],
        }
    )


def scope_for_agent3(extraction: ExtractionOutput) -> ExtractionOutput:
    """Primary diagnosis + medication list (+ source spans on meds)."""
    return extraction.model_copy(
        update={
            "patient_name": None,
            "discharge_date": None,
            "primary_diagnosis_source": None,
            "secondary_diagnoses": [],
            "procedures_performed": [],
            "follow_up_appointments": [],
            "activity_restrictions": [],
            "dietary_restrictions": [],
            "red_flag_symptoms": [],
            "discharge_condition": None,
            "extraction_warnings": [],
        }
    )


def scope_for_agent4(extraction: ExtractionOutput) -> ExtractionOutput:
    """Recovery: diagnosis, procedures, activity restrictions only."""
    return extraction.model_copy(
        update={
            "patient_name": None,
            "discharge_date": None,
            "primary_diagnosis_source": None,
            "secondary_diagnoses": [],
            "medications": [],
            "follow_up_appointments": [],
            "dietary_restrictions": [],
            "red_flag_symptoms": [],
            "discharge_condition": None,
            "extraction_warnings": [],
        }
    )


def scope_for_agent5(extraction: ExtractionOutput) -> ExtractionOutput:
    """Escalation: diagnosis, red flags, secondaries, medications only."""
    return extraction.model_copy(
        update={
            "patient_name": None,
            "discharge_date": None,
            "primary_diagnosis_source": None,
            "procedures_performed": [],
            "follow_up_appointments": [],
            "activity_restrictions": [],
            "dietary_restrictions": [],
            "discharge_condition": None,
            "extraction_warnings": [],
        }
    )
