"""
Pipeline orchestrator for DischargeIQ.

Wires all five agents in sequence and aggregates their outputs into a
PipelineResponse. Agents 2-5 are stubbed until their tickets land;
Agent 1 is fully live and runs on every request.

Depends on: dischargeiq.agents.extraction_agent,
            dischargeiq.models.extraction, dischargeiq.models.pipeline,
            dischargeiq.utils.warnings.
"""

import logging

from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.models.pipeline import PipelineResponse
from dischargeiq.utils.warnings import assess_extraction_completeness

logger = logging.getLogger(__name__)


def run_pipeline(pdf_path: str) -> PipelineResponse:
    """
    Run the multi-agent discharge pipeline on a PDF file path.

    Currently live: Agent 1 (extraction).
    Stubbed (empty string): Agents 2-5 — wired in Sprint 2.

    Data contract: Agent 1 returns ExtractionOutput (locked schema).
    All downstream agents will receive that model as input. Never change
    field names in ExtractionOutput without full team sign-off.

    On any agent failure the pipeline sets pipeline_status="partial" and
    returns whatever was successfully extracted — it never raises to the
    caller.

    Args:
        pdf_path: Absolute path to a temporary PDF written by the API layer.

    Returns:
        PipelineResponse: Aggregated outputs. pipeline_status is "complete"
        when Agent 1 succeeds; "partial" on any failure.
    """
    # ── Agent 1 — Extraction ─────────────────────────────────────────────────
    # Produces the ExtractionOutput that all downstream agents consume.
    # On failure, fall back to a minimal stub so the API never returns 500.
    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        extraction = run_extraction_agent(pdf_text)
        pipeline_status = "complete"
    except Exception as exc:
        logger.error("Agent 1 failed for %s: %s", pdf_path, exc)
        extraction = ExtractionOutput(
            primary_diagnosis="Extraction failed",
            extraction_warnings=[
                f"Agent 1 error — could not extract document: {type(exc).__name__}: {exc}"
            ],
        )
        pipeline_status = "partial"

    # ── Completeness check ────────────────────────────────────────────────────
    # assess_extraction_completeness flags missing fields (no meds, no follow-ups, etc.)
    # and returns human-readable warning strings for the response.
    completeness = assess_extraction_completeness(extraction)
    extraction_warnings = completeness["warning_messages"]

    # If completeness warnings were raised, downgrade status to partial.
    if completeness["has_warnings"] and pipeline_status == "complete":
        pipeline_status = "partial"

    # ── Agents 2-5 — Stubs (Sprint 2) ────────────────────────────────────────
    # Each agent will receive `extraction` as its primary input.
    # Placeholder empty strings keep PipelineResponse valid today.
    diagnosis_explanation = ""   # Agent 2 (DIS-9)
    medication_rationale = ""    # Agent 3 (DIS-12)
    recovery_trajectory = ""     # Agent 4 (DIS-16)
    escalation_guide = ""        # Agent 5 (DIS-22)
    fk_scores: dict = {}         # Populated when agents 2-5 are live

    return PipelineResponse(
        extraction=extraction,
        diagnosis_explanation=diagnosis_explanation,
        medication_rationale=medication_rationale,
        recovery_trajectory=recovery_trajectory,
        escalation_guide=escalation_guide,
        fk_scores=fk_scores,
        extraction_warnings=extraction_warnings,
        pipeline_status=pipeline_status,
    )
