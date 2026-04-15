"""
Pipeline orchestrator for DischargeIQ.

Wires all five agents in sequence and aggregates their outputs into a
PipelineResponse. Full agent implementations are added in later tickets;
until then, run_pipeline returns a valid partial stub so POST /analyze
never crashes.

Depends on: dischargeiq.models.extraction, dischargeiq.models.pipeline,
            dischargeiq.agents.extraction_agent (DIS-5),
            dischargeiq.agents.diagnosis_agent (DIS-8).
"""

import logging

from dischargeiq.agents.extraction_agent import run_extraction_agent, extract_text_from_pdf
from dischargeiq.agents.diagnosis_agent import run_diagnosis_agent
from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.models.pipeline import PipelineResponse

logger = logging.getLogger(__name__)


def run_pipeline(pdf_path: str) -> PipelineResponse:
    """
    Run the multi-agent discharge pipeline on a PDF file path.

    Args:
        pdf_path: Absolute path to a temporary PDF written by the API layer.

    Returns:
        PipelineResponse: Aggregated extraction and agent text outputs.
        pipeline_status is "complete" when all agents succeed, or "partial"
        when one or more agents failed with a fallback message.

    Note:
        Agent handoff contract: Agent 1 output (ExtractionOutput) is passed
        directly to Agent 2. If Agent 1 fails, pipeline_status is set to
        "partial" and downstream agents are skipped per project rules.
    """
    diagnosis_explanation = ""
    fk_scores = {}
    pipeline_status = "partial"

    # ── Agent 1: Extraction ────────────────────────────────────────────────────
    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        extraction = run_extraction_agent(pdf_text)
        logger.info("Agent 1 complete: %s", extraction.primary_diagnosis)
    except Exception as e:
        logger.error("Agent 1 failed: %s", e)
        # Return early with stub — downstream agents cannot run without extraction
        extraction = ExtractionOutput(
            primary_diagnosis="(Extraction failed)",
            extraction_warnings=[f"Agent 1 error: {e}"],
        )
        return PipelineResponse(
            extraction=extraction,
            diagnosis_explanation="",
            medication_rationale="",
            recovery_trajectory="",
            escalation_guide="",
            fk_scores={},
            extraction_warnings=extraction.extraction_warnings,
            pipeline_status="partial",
        )

    # ── Agent 2: Diagnosis Explanation ─────────────────────────────────────────
    try:
        doc_id = pdf_path.split("/")[-1]  # Use filename as document identifier
        agent2_result = run_diagnosis_agent(extraction, document_id=doc_id)
        diagnosis_explanation = agent2_result["text"]
        fk_scores["diagnosis"] = agent2_result["fk_grade"]
        logger.info("Agent 2 complete: FK grade %.2f", agent2_result["fk_grade"])
        pipeline_status = "complete"
    except Exception as e:
        logger.error("Agent 2 failed: %s", e)
        diagnosis_explanation = ""
        pipeline_status = "partial"

    # ── Agents 3–5: Stubs (implemented in DIS-9, DIS-12, DIS-13) ──────────────
    return PipelineResponse(
        extraction=extraction,
        diagnosis_explanation=diagnosis_explanation,
        medication_rationale="",
        recovery_trajectory="",
        escalation_guide="",
        fk_scores=fk_scores,
        extraction_warnings=extraction.extraction_warnings,
        pipeline_status=pipeline_status,
    )
