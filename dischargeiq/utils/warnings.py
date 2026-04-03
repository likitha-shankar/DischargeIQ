"""
Extraction completeness checker for DischargeIQ.

Called after Agent 1 to flag fields that are missing or empty.
The warnings are stored in extraction_warnings on the PipelineResponse
and surfaced to the user so they know what data may be incomplete.

Depends on: dischargeiq.models.extraction.
"""

from dischargeiq.models.extraction import ExtractionOutput


def assess_extraction_completeness(extraction: ExtractionOutput) -> dict:
    """
    Check an ExtractionOutput for missing or empty fields and return status.

    Each warning is a human-readable string describing what is missing.
    These are informational — a missing field does not block the pipeline.

    Args:
        extraction: Validated output from Agent 1.

    Returns:
        dict with keys:
            has_warnings (bool): True if any warning was generated.
            is_partial (bool): True if extraction looks incomplete (same as
                has_warnings for this heuristic).
            warning_messages (list[str]): Human-readable warning strings.

    """
    warning_messages = []

    if not extraction.primary_diagnosis:
        warning_messages.append("Missing primary diagnosis.")
    if not extraction.medications:
        warning_messages.append("No medications extracted.")
    if not extraction.follow_up_appointments:
        warning_messages.append("No follow-up appointments extracted.")
    if not extraction.red_flag_symptoms:
        warning_messages.append("No red-flag symptoms extracted.")
    if not extraction.activity_restrictions and not extraction.dietary_restrictions:
        warning_messages.append("No activity or dietary restrictions extracted.")
    if not extraction.discharge_date:
        warning_messages.append("Missing discharge date.")
    if not extraction.patient_name:
        warning_messages.append("Missing patient name.")

    has_warnings = len(warning_messages) > 0
    return {
        "has_warnings": has_warnings,
        "is_partial": has_warnings,
        "warning_messages": warning_messages,
    }
