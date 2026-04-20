"""
Pipeline orchestrator for DischargeIQ.

Wires all five agents in sequence and aggregates their outputs into a
PipelineResponse. Agents 1-4 are fully live. Agent 5 is stubbed until
DIS-22 lands.

Depends on: dischargeiq.agents.extraction_agent (DIS-5),
            dischargeiq.agents.diagnosis_agent (DIS-8),
            dischargeiq.agents.medication_agent (DIS-12),
            dischargeiq.agents.recovery_agent (DIS-16),
            dischargeiq.db.history, dischargeiq.models.extraction,
            dischargeiq.models.pipeline, dischargeiq.utils.warnings.
"""

import hashlib
import logging
import os
import time
import uuid

from dischargeiq.agents.diagnosis_agent import run_diagnosis_agent
from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.agents.medication_agent import run_medication_agent
from dischargeiq.agents.recovery_agent import run_recovery_agent
from dischargeiq.db.history import get_db_pool, save_discharge_history
from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.models.pipeline import PipelineResponse
from dischargeiq.utils.warnings import assess_extraction_completeness

logger = logging.getLogger(__name__)


async def run_pipeline(
    pdf_path: str, session_id: str | None = None
) -> PipelineResponse:
    """
    Run the multi-agent discharge pipeline on a PDF file path.

    Currently live: Agent 1 (extraction), Agent 2 (diagnosis explanation),
    Agent 3 (medication rationale), Agent 4 (recovery trajectory).
    Agent 5 is stubbed — wired when DIS-22 lands.

    Data contract: Agent 1 returns ExtractionOutput (locked schema).
    All downstream agents receive that model as input. Never change
    field names in ExtractionOutput without full team sign-off.

    On any agent failure the pipeline sets pipeline_status="partial" and
    returns whatever was successfully extracted — it never raises to the
    caller.

    Args:
        pdf_path: Absolute path to a temporary PDF written by the API layer.
        session_id: Optional session identifier propagated to the DB row;
                    a fresh UUID is generated when omitted.

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

    agent1_succeeded = extraction.primary_diagnosis not in (
        None, "", "Extraction failed"
    )

    fk_scores: dict = {}

    # ── Agent 2 — Diagnosis Explanation ─────────────────────────────────────
    # Accepts ExtractionOutput from Agent 1.
    # Returns dict with keys: text, fk_grade, passes.
    # Runs whenever Agent 1 produced a real diagnosis — independent of whether
    # the completeness check downgraded pipeline_status to "partial". A document
    # can be incomplete (missing follow-ups, activity restrictions, etc.) and
    # still have a valid diagnosis worth explaining to the patient.
    diagnosis_explanation = ""

    if agent1_succeeded:
        try:
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
            fk_scores["agent2"] = {
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

    # ── Agent 3 — Medication Rationale ───────────────────────────────────────
    # Data contract: receives the full ExtractionOutput from Agent 1.
    # Returns dict with keys: text, fk_grade, passes.
    medication_rationale = ""

    if agent1_succeeded:
        try:
            agent3_result = run_medication_agent(
                extraction=extraction,
                document_id=pdf_path,
            )
            medication_rationale = agent3_result["text"]
            fk_scores["agent3"] = {
                "fk_grade": agent3_result["fk_grade"],
                "passes": agent3_result["passes"],
            }
            logger.info(
                "Agent 3 complete — FK grade: %.2f, passes: %s",
                agent3_result["fk_grade"],
                agent3_result["passes"],
            )
        except Exception as exc:
            logger.error("Agent 3 failed for %s: %s", pdf_path, exc)
            medication_rationale = ""
            pipeline_status = "partial"

    # ── Agent 4 — Recovery Trajectory ────────────────────────────────────────
    # Data contract: receives the full ExtractionOutput from Agent 1.
    # Returns dict with keys: text, fk_grade, passes.
    recovery_trajectory = ""

    if agent1_succeeded:
        try:
            agent4_result = run_recovery_agent(
                extraction=extraction,
                document_id=pdf_path,
            )
            recovery_trajectory = agent4_result["text"]
            fk_scores["agent4"] = {
                "fk_grade": agent4_result["fk_grade"],
                "passes": agent4_result["passes"],
            }
            logger.info(
                "Agent 4 complete — FK grade: %.2f, passes: %s",
                agent4_result["fk_grade"],
                agent4_result["passes"],
            )
        except Exception as exc:
            logger.error("Agent 4 failed for %s: %s", pdf_path, exc)
            recovery_trajectory = ""
            pipeline_status = "partial"

    # ── Agent 5 — Stub (Sprint 2) ────────────────────────────────────────────
    # Agent 5 (escalation) is tracked by DIS-22.
    escalation_guide = ""        # Agent 5 (DIS-22)

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

    response = PipelineResponse(
        extraction=extraction,
        diagnosis_explanation=diagnosis_explanation,
        medication_rationale=medication_rationale,
        recovery_trajectory=recovery_trajectory,
        escalation_guide=escalation_guide,
        fk_scores=fk_scores,
        extraction_warnings=extraction_warnings,
        pipeline_status=pipeline_status,
    )

    # ── DB write (non-fatal) ────────────────────────────────────────────────
    # Persist one row per pipeline run so the history screen can list past
    # summaries. The DB write is wrapped in try/except — a Neon outage or
    # schema drift must never crash the pipeline or block the UI response.
    db_session_id = session_id or str(uuid.uuid4())
    try:
        with open(pdf_path, "rb") as pdf_file:
            document_hash = hashlib.sha256(pdf_file.read()).hexdigest()
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL not set")
        pool = await get_db_pool(database_url)
        try:
            await save_discharge_history(
                pool=pool,
                session_id=db_session_id,
                document_hash=document_hash,
                extraction=extraction,
                fk_scores=fk_scores,
                pipeline_status=pipeline_status,
            )
            logger.info(
                "Discharge history saved — session: %s", db_session_id
            )
        finally:
            await pool.close()
    except Exception as exc:
        logger.warning(
            "DB write failed (non-fatal) — session: %s — %s",
            db_session_id,
            exc,
        )

    return response
