"""
Extraction completeness checker for DischargeIQ.

Called after Agent 1 to flag fields that are missing or empty. Warnings
are split into two severities:

  * critical  — the document almost certainly is not a real discharge
                summary (no diagnosis / no meds / no red-flag symptoms).
                Orchestrator downgrades pipeline_status to "partial".
  * advisory  — common gaps on otherwise valid discharges (no follow-up
                appointment, no patient name, etc.). Orchestrator promotes
                pipeline_status to "complete_with_warnings" so the UI can
                show a softer "Verified*" pill with a tooltip.

Depends on: dischargeiq.models.extraction.
"""

from dischargeiq.models.extraction import ExtractionOutput


def _likely_not_discharge_summary(critical_warnings: list[str]) -> bool:
    """
    Heuristically flag uploads that likely are not discharge summaries.

    Args:
        critical_warnings: Critical completeness warnings already computed.

    Returns:
        bool: True when two or more critical discharge-defining fields are
            missing (diagnosis, medications, red-flag symptoms).
    """
    return len(critical_warnings) >= 2


def assess_extraction_completeness(extraction: ExtractionOutput) -> dict:
    """
    Check an ExtractionOutput for missing fields and classify them by severity.

    Args:
        extraction: Validated output from Agent 1.

    Returns:
        dict with keys:
            critical_warnings (list[str]): Missing fields that invalidate
                the summary (primary_diagnosis, medications, red_flag_symptoms).
            advisory_warnings (list[str]): Missing fields that are common
                on valid discharges (follow-ups, activity/diet, dates, name).
            warning_messages (list[str]): Union of both — kept for callers
                that only want the flat list for display.
            has_warnings (bool): True iff either list is non-empty.
            is_critical  (bool): True iff critical_warnings is non-empty.
            is_partial   (bool): Alias of is_critical, retained so any
                older caller keying on this flag still behaves the same
                way (partial == "document not usable", same as critical).
    """
    critical_warnings: list[str] = []
    advisory_warnings: list[str] = []

    # ── Critical — three fields that together define a real discharge ──
    # A document missing any of these is almost certainly not a discharge
    # summary (could be an intake form, a consent page, or a non-clinical
    # PDF). Downstream agents have nothing meaningful to say without them.
    if not extraction.primary_diagnosis:
        critical_warnings.append("Missing primary diagnosis.")
    if not extraction.medications:
        critical_warnings.append("No medications extracted.")
    if not extraction.red_flag_symptoms:
        critical_warnings.append("No red-flag symptoms extracted.")

    if _likely_not_discharge_summary(critical_warnings):
        critical_warnings.append(
            "This file may not be a hospital discharge summary. "
            "Please upload a discharge summary PDF."
        )

    # ── Advisory — common gaps on real, usable discharges ──
    # These are worth surfacing to the patient (so they know the summary
    # is incomplete) but they do not invalidate the extraction.
    if not extraction.follow_up_appointments:
        advisory_warnings.append("No follow-up appointments extracted.")
    if not extraction.activity_restrictions and not extraction.dietary_restrictions:
        advisory_warnings.append("No activity or dietary restrictions extracted.")
    if not extraction.discharge_date:
        advisory_warnings.append("Missing discharge date.")
    if not extraction.patient_name:
        advisory_warnings.append("Missing patient name.")

    has_warnings = bool(critical_warnings) or bool(advisory_warnings)
    is_critical = bool(critical_warnings)

    return {
        "critical_warnings": critical_warnings,
        "advisory_warnings": advisory_warnings,
        "warning_messages": critical_warnings + advisory_warnings,
        "has_warnings": has_warnings,
        "is_critical": is_critical,
        "is_partial": is_critical,
    }
