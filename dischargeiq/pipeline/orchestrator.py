"""
Pipeline orchestrator for DischargeIQ.

Wires all five agents in sequence and aggregates their outputs into a
PipelineResponse. Agents 1 and 2 are fully live. Agents 3-5 are stubbed
until their tickets land.

Depends on: dischargeiq.agents.extraction_agent,
            dischargeiq.models.extraction, dischargeiq.models.pipeline,
            dischargeiq.utils.warnings.
"""

import logging
import time

from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.models.pipeline import PipelineResponse
from dischargeiq.utils.warnings import assess_extraction_completeness

logger = logging.getLogger(__name__)


def run_pipeline(pdf_path: str) -> PipelineResponse:
    """
    Run the multi-agent discharge pipeline on a PDF file path.

    Currently live: Agent 1 (extraction), Agent 2 (diagnosis explanation).
    Stubbed (empty string): Agents 3-5 — wired in Sprint 2.

    Data contract: Agent 1 returns ExtractionOutput (locked schema).
    All downstream agents receive that model as input. Never change
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
    pipeline_start = time.monotonic()
    logger.info("Pipeline start — document: %s", pdf_path)

    # ── Agent 1 — Extraction ─────────────────────────────────────────────────
    # Produces the ExtractionOutput that all downstream agents consume.
    # On failure, fall back to a minimal stub so the API never returns 500.
    try:
        pdf_text = extract_text_from_pdf(pdf_path)
        extraction = run_extraction_agent(pdf_text)
        pipeline_status = "complete"
        logger.info("Agent 1 complete — primary_diagnosis: '%s'", extraction.primary_diagnosis)
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
        logger.warning(
            "Pipeline completeness warnings for %s: %s",
            pdf_path,
            extraction_warnings,
        )

    # ── Agent 2 — Diagnosis Explanation ─────────────────────────────────────
    # Accepts ExtractionOutput from Agent 1.
    # Returns dict with keys: text, fk_grade, passes.
    # Runs whenever Agent 1 produced a real diagnosis — independent of whether
    # the completeness check downgraded pipeline_status to "partial". A document
    # can be incomplete (missing follow-ups, activity restrictions, etc.) and
    # still have a valid diagnosis worth explaining to the patient.
    diagnosis_explanation = ""
    agent2_fk: dict = {}

    # Gate on diagnosis validity only — not on pipeline_status — so completeness
    # warnings for missing fields don't block the explanation from running.
    agent1_succeeded = extraction.primary_diagnosis not in (
        None, "", "Extraction failed"
    )

    if agent1_succeeded:
        try:
            from dischargeiq.agents.diagnosis_agent import run_diagnosis_agent
            # Explicitly strip inpatient-only fields before handing the
            # extraction to Agent 2. procedures_performed contains IV drugs
            # and imaging findings from the hospital stay that the patient
            # was NOT discharged on — letting Agent 2 see them caused the
            # explanation text to invent treatments (e.g. "X-ray showed
            # your lungs were swollen", "methylprednisolone"). Agent 2
            # should reason only about the discharge diagnoses and the
            # discharge medication list; anything else is inpatient
            # context, not patient-facing discharge education.
            agent2_input = extraction.model_copy(
                update={"procedures_performed": []}
            )
            agent2_result = run_diagnosis_agent(
                extraction=agent2_input,
                document_id=pdf_path,
            )
            diagnosis_explanation = agent2_result["text"]
            agent2_fk = {
                "fk_grade": agent2_result["fk_grade"],
                "passes": agent2_result["passes"],
            }
            logger.info(
                "Agent 2 complete — FK grade: %.2f, passes: %s",
                agent2_result["fk_grade"],
                agent2_result["passes"],
            )
        except Exception as exc:
            logger.error("Agent 2 failed for %s: %s", pdf_path, exc)
            diagnosis_explanation = ""
            pipeline_status = "partial"

    # ── Agents 3-5 — Stubs (Sprint 2) ────────────────────────────────────────
    # Each agent will receive `extraction` as its primary input.
    # Placeholder empty strings keep PipelineResponse valid today.
    medication_rationale = ""    # Agent 3 (DIS-12)
    recovery_trajectory = ""     # Agent 4 (DIS-16)
    escalation_guide = ""        # Agent 5 (DIS-22)
    fk_scores: dict = {"agent2": agent2_fk} if agent2_fk else {}

    elapsed = time.monotonic() - pipeline_start

    if pipeline_status == "partial":
        logger.warning(
            "Pipeline complete (partial) — %s — %.2fs", pdf_path, elapsed
        )
    else:
        logger.info(
            "Pipeline complete — %s — status: %s, %.2fs",
            pdf_path,
            pipeline_status,
            elapsed,
        )

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
