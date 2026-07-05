"""
File: dischargeiq/utils/extraction_scope.py
Owner: Likitha Shankar
Description: Builds narrowed ExtractionOutput copies for Agents 2–5 so each LLM user
  message only includes fields that agent is allowed to see — reducing tokens and
  hallucination surface (e.g. Agent 2 excludes procedures/meds; Agent 3 keeps meds).
Key functions/classes: scope_for_agent2, scope_for_agent3, scope_for_agent4, scope_for_agent5
Edge cases handled:
  - Clears unrelated lists/fields to [] or None via model_copy(update=...) consistently.
Dependencies: dischargeiq.models.extraction.ExtractionOutput
Called by: dischargeiq.pipeline.orchestrator (before each downstream agent run).
"""

from dischargeiq.models.extraction import ExtractionOutput

_CLEARED: dict = {
    "patient_name": None,
    "discharge_date": None,
    "primary_diagnosis_source": None,
    "secondary_diagnoses": [],
    "procedures_performed": [],
    "medications": [],
    "follow_up_appointments": [],
    "activity_restrictions": [],
    "dietary_restrictions": [],
    "red_flag_symptoms": [],
    "discharge_condition": None,
    "extraction_warnings": [],
}


def scope_for_agent2(extraction: ExtractionOutput) -> ExtractionOutput:
    """Primary + secondary diagnoses only."""
    return extraction.model_copy(update={**_CLEARED, "secondary_diagnoses": extraction.secondary_diagnoses})


def scope_for_agent3(extraction: ExtractionOutput) -> ExtractionOutput:
    """Primary diagnosis + medication list."""
    return extraction.model_copy(update={**_CLEARED, "medications": extraction.medications})


def scope_for_agent4(extraction: ExtractionOutput) -> ExtractionOutput:
    """Recovery: diagnosis, procedures, restrictions, red flags, discharge condition."""
    return extraction.model_copy(update={
        **_CLEARED,
        "procedures_performed": extraction.procedures_performed,
        "activity_restrictions": extraction.activity_restrictions,
        "dietary_restrictions": extraction.dietary_restrictions,
        "red_flag_symptoms": extraction.red_flag_symptoms,
        "discharge_condition": extraction.discharge_condition,
    })


def scope_for_agent5(extraction: ExtractionOutput) -> ExtractionOutput:
    """Escalation: diagnosis, red flags, secondaries, medications."""
    return extraction.model_copy(update={
        **_CLEARED,
        "secondary_diagnoses": extraction.secondary_diagnoses,
        "medications": extraction.medications,
        "red_flag_symptoms": extraction.red_flag_symptoms,
    })
