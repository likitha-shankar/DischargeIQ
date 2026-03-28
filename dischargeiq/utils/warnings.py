"""
Extraction completeness checker for DischargeIQ.

Called after Agent 1 to flag fields that are missing or empty.
The warnings are stored in extraction_warnings on the PipelineResponse
and surfaced to the user so they know what data may be incomplete.

Depends on: dischargeiq.models.extraction.
"""

from dischargeiq.models.extraction import ExtractionOutput


def assess_extraction_completeness(extraction: ExtractionOutput) -> list[str]:
    """
    Check an ExtractionOutput for missing or empty fields and return warnings.

    Each warning is a human-readable string describing what is missing.
    These are informational — a missing field does not block the pipeline.

    Args:
        extraction: Validated output from Agent 1.

    Returns:
        list[str]: Warning messages for any fields that are null or empty.
    """
    warnings = []

    if not extraction.primary_diagnosis:
        warnings.append("Missing primary diagnosis.")
    if not extraction.medications:
        warnings.append("No medications extracted.")
    if not extraction.follow_up_appointments:
        warnings.append("No follow-up appointments extracted.")
    if not extraction.red_flag_symptoms:
        warnings.append("No red-flag symptoms extracted.")
    if not extraction.activity_restrictions and not extraction.dietary_restrictions:
        warnings.append("No activity or dietary restrictions extracted.")
    if not extraction.discharge_date:
        warnings.append("Missing discharge date.")
    if not extraction.patient_name:
        warnings.append("Missing patient name.")

    return warnings
