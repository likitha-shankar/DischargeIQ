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
    """Recovery: diagnosis, procedures, restrictions, red flags, and discharge condition."""
    return extraction.model_copy(
        update={
            "patient_name": None,
            "discharge_date": None,
            "primary_diagnosis_source": None,
            "medications": [],
            "follow_up_appointments": [],
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
