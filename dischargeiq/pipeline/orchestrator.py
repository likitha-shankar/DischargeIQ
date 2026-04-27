"""
File: dischargeiq/pipeline/orchestrator.py
Owner: Likitha Shankar
Description: Async coordinator for PDF→text extraction, Agents 1–5, optional Agent 6,
  and Neon history persistence — wraps each agent in try/except, scopes extraction per
  agent via extraction_scope, injects safety_context sentences into Agent 3 input from
  raw PDF text, and sets pipeline_status from completeness + failure state.
Key functions/classes: run_pipeline, _run_pipeline_internal, _extract_safety_context,
  _save_history_with_retries
Edge cases handled:
  - Per-agent failures return partial pipeline with empties; 300s asyncio timeout;
  - DB save retried; completeness critical vs advisory drives status; simulator errors non-fatal.
Dependencies: all dischargeiq.agents.*, dischargeiq.db.history, dischargeiq.models.*,
  dischargeiq.utils.extraction_scope, dischargeiq.utils.warnings
Called by: dischargeiq.main (/analyze), scripts/stress/run_stress_fixtures.py, slow corpus tests.
"""

import asyncio
import hashlib
import logging
import os
import re
import time
import uuid
from datetime import datetime
from typing import Callable

from dischargeiq.agents.diagnosis_agent import run_diagnosis_agent
from dischargeiq.agents.escalation_agent import run_escalation_agent
from dischargeiq.agents.extraction_agent import extract_text_from_pdf, run_extraction_agent
from dischargeiq.agents.patient_simulator_agent import run_patient_simulator_agent
from dischargeiq.agents.medication_agent import run_medication_agent
from dischargeiq.agents.recovery_agent import run_recovery_agent
from dischargeiq.db.history import get_db_pool, save_discharge_history
from dischargeiq.models.extraction import ExtractionOutput, FollowUpAppointment
from dischargeiq.models.pipeline import PipelineResponse
from dischargeiq.utils.extraction_scope import (
    scope_for_agent2,
    scope_for_agent3,
    scope_for_agent4,
    scope_for_agent5,
)
from dischargeiq.utils.warnings import assess_extraction_completeness

logger = logging.getLogger(__name__)

_APPT_DATE_FORMATS = (
    "%Y-%m-%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d %B %Y",
    "%d %b %Y",
)


def _parse_appt_date(appt: FollowUpAppointment) -> datetime:
    """
    Parse appointment date string to datetime for sorting (soonest first).

    Handles common discharge-summary formats. Unparseable or missing dates
    sort last so they do not appear before real dates.
    """
    raw = appt.date
    if not raw or not str(raw).strip():
        return datetime.max
    s = str(raw).strip()
    for fmt in _APPT_DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.max


# Trigger phrases for _extract_safety_context — matched case-insensitively
# against each sentence of the raw discharge text. The list mirrors the
# CRITICAL SAFETY LANGUAGE block in prompts/agent3_system_prompt.txt so the
# LLM receives exactly the sentences it is expected to reproduce verbatim.
_SAFETY_TRIGGERS = re.compile(
    r"do not stop|never stop|stopping suddenly|stopping can cause|"
    r"call 911|go to the er|face drooping|arm weakness|"
    r"trouble speaking|signs of stroke|stroke|emergency",
    flags=re.IGNORECASE,
)

# Hard cap on how many safety sentences we forward to Agent 3. Prevents a
# pathological document (e.g. a long consent form pasted into the summary)
# from pushing out the medication block in the user message.
_SAFETY_MAX_SENTENCES = 10

# Pipeline-wide wall-clock cap. Five agents at p95 ~20s each plus pdfplumber
# and a DB write comfortably fit inside this budget; anything past 300s is
# a stuck LLM call worth surfacing to the caller as a 504.
_PIPELINE_TIMEOUT_SECONDS = 300.0


async def _save_history_with_retries(
    database_url: str,
    session_id: str,
    document_hash: str,
    extraction: ExtractionOutput,
    fk_scores: dict,
    pipeline_status: str,
) -> None:
    """
    Persist one discharge_history row with short retries for transient outages.

    Args:
        database_url: Database connection string from DATABASE_URL.
        session_id: Session identifier for the row.
        document_hash: SHA-256 hash of the source PDF.
        extraction: Agent 1 extraction payload.
        fk_scores: Aggregated FK score dict for agents 2-5.
        pipeline_status: Final pipeline status string.

    Raises:
        Exception: Re-raises the final persistence error after retries.
    """
    max_attempts = 3
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            pool = await get_db_pool(database_url)
            try:
                await save_discharge_history(
                    pool=pool,
                    session_id=session_id,
                    document_hash=document_hash,
                    extraction=extraction,
                    fk_scores=fk_scores,
                    pipeline_status=pipeline_status,
                )
                return
            finally:
                await pool.close()
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                await asyncio.sleep(float(attempt))
    if last_error is not None:
        raise last_error


def _extract_safety_context(raw_text: str) -> str:
    """
    Scan the full discharge document text for emergency / critical-safety
    language and return matching sentences as a newline-joined block.

    Why this exists:
        Agent 3's per-drug user message only carries the Medication.source
        span captured by Agent 1, which is typically the drug's own line
        in the medication list. When a discharge PDF puts a stroke / 911
        warning in a separate `EMERGENCY` section (e.g. adv_06 warfarin),
        that text never reaches Agent 3, so the CRITICAL SAFETY LANGUAGE
        rule in agent3_system_prompt.txt cannot fire. This helper harvests
        that cross-section language once and passes it to Agent 3 as a
        document-wide `safety_context` block.

    Args:
        raw_text: Full pdfplumber-extracted text from the PDF. May be
                  empty if Agent 1 extraction failed upstream.

    Returns:
        str: Up to _SAFETY_MAX_SENTENCES matching sentences joined by
             newlines. Empty string when nothing matches or on any error
             — callers must treat an empty result as "no safety block"
             rather than as a failure.
    """
    if not raw_text:
        return ""

    try:
        # Split on period OR newline so list-style warnings ("DO NOT STOP")
        # and sentence-style warnings ("Stopping can cause stroke.") both
        # survive as standalone candidates. Bullets and headings come
        # through as their own lines already.
        matches: list[str] = []
        for candidate in re.split(r"[.\n]", raw_text):
            sentence = candidate.strip()
            if sentence and _SAFETY_TRIGGERS.search(sentence):
                matches.append(sentence)
                if len(matches) >= _SAFETY_MAX_SENTENCES:
                    break
        return "\n".join(matches)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("safety context scan failed: %s", exc)
        return ""


async def run_pipeline(
    pdf_path: str,
    session_id: str | None = None,
    on_progress: Callable[[int, str, str], None] | None = None,
) -> PipelineResponse:
    """
    Public entry point — wraps _run_pipeline_internal in a 300-second
    wall-clock timeout so a stuck LLM call cannot hang the API worker
    forever. On timeout, asyncio.TimeoutError is allowed to propagate;
    main.py translates it to an HTTP 504 for the client.
    """
    return await asyncio.wait_for(
        _run_pipeline_internal(pdf_path, session_id, on_progress),
        timeout=_PIPELINE_TIMEOUT_SECONDS,
    )


async def _run_pipeline_internal(
    pdf_path: str,
    session_id: str | None = None,
    on_progress: Callable[[int, str, str], None] | None = None,
) -> PipelineResponse:
    """
    Run the multi-agent discharge pipeline on a PDF file path.

    All five agents are live: Agent 1 (extraction), Agent 2 (diagnosis
    explanation), Agent 3 (medication rationale), Agent 4 (recovery
    trajectory), Agent 5 (escalation / warning-signs).

    Data contract: Agent 1 returns ExtractionOutput (locked schema).
    Agents 2–5 each receive a **scoped** copy (see `utils/extraction_scope.py`)
    with only the fields that agent’s prompt uses, to save tokens and reduce
    cross-field confusion. Never change ExtractionOutput field names without
    full team sign-off.

    On any agent failure the pipeline sets pipeline_status="partial" and
    returns whatever was successfully extracted — it never raises to the
    caller (except for the wall-clock timeout enforced by run_pipeline).

    Args:
        pdf_path: Absolute path to a temporary PDF written by the API layer.
        session_id: Optional session identifier propagated to the DB row;
                    a fresh UUID is generated when omitted.

    Returns:
        PipelineResponse: Aggregated outputs. pipeline_status is "complete"
        when Agent 1 succeeds and no gaps were flagged; "complete_with_warnings"
        when only advisory completeness warnings fired; "partial" on any
        critical gap or downstream agent failure.
    """
    pipeline_start = time.monotonic()
    logger.info("Pipeline start — document: %s", pdf_path)

    # ── Agent 1 — Extraction ─────────────────────────────────────────────────
    if on_progress is not None:
        on_progress(1, "Extraction", "Reading your discharge document...")
    # Produces the ExtractionOutput that all downstream agents consume.
    # On failure, fall back to a minimal stub so the API never returns 500.
    # pdf_text is initialised here (not inside try) so that downstream steps
    # — notably _extract_safety_context before Agent 3 — can reference it
    # unconditionally even if the text extraction step raised.
    pdf_text = ""
    try:
        # Each agent's LLM client (Anthropic / OpenAI / OpenRouter) is
        # synchronous and blocks the FastAPI event loop while waiting on the
        # network. With six sequential agents at 5–15 s each, that starves
        # the /progress poller in the loading iframe — the bar appears
        # frozen even though the pipeline is making progress. asyncio.to_thread
        # offloads each blocking call to the default thread pool so the
        # event loop can keep serving /progress in real time.
        pdf_text = await asyncio.to_thread(extract_text_from_pdf, pdf_path)
        extraction = await asyncio.to_thread(run_extraction_agent, pdf_text)
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

    # Soonest follow-ups first — document order is not always chronological.
    if extraction.follow_up_appointments:
        extraction = extraction.model_copy(
            update={
                "follow_up_appointments": sorted(
                    extraction.follow_up_appointments,
                    key=_parse_appt_date,
                )
            }
        )

    # ── Completeness check ────────────────────────────────────────────────────
    # assess_extraction_completeness splits missing fields into:
    #   critical  — primary_diagnosis / medications / red_flag_symptoms missing
    #               means this likely isn't a real discharge document, so we
    #               downgrade status to "partial".
    #   advisory  — common gaps on valid discharges (no follow-ups, missing
    #               patient name, etc.). We promote to "complete_with_warnings"
    #               so the UI can show a softer "Verified*" pill instead of
    #               the alarming amber "Incomplete" one.
    # Agent failures downstream (A2–A5) still set "partial" directly on their
    # own except path — a crashed agent is always a real failure.
    completeness = assess_extraction_completeness(extraction)
    # Preserve deterministic Agent 1 warnings (e.g. short-document,
    # conflicting-dose) and append completeness-classification warnings.
    # Previous behavior overwrote Agent 1 warnings with completeness-only
    # messages, which hid safety-relevant extraction signals.
    extraction_warnings = list(extraction.extraction_warnings)
    for warning in completeness["warning_messages"]:
        if warning not in extraction_warnings:
            extraction_warnings.append(warning)

    if completeness["is_critical"] and pipeline_status == "complete":
        pipeline_status = "partial"
        logger.warning(
            "Pipeline critical completeness failure for %s: %s",
            pdf_path,
            completeness["critical_warnings"],
        )
    elif completeness["advisory_warnings"] and pipeline_status == "complete":
        pipeline_status = "complete_with_warnings"
        logger.info(
            "Pipeline advisory completeness warnings for %s: %s",
            pdf_path,
            completeness["advisory_warnings"],
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
            if on_progress is not None:
                on_progress(2, "Diagnosis", "Understanding your diagnosis...")
            # Explicitly strip inpatient-only fields before handing the
            # extraction to Agent 2. procedures_performed contains IV drugs
            # and imaging findings from the hospital stay that the patient
            # was NOT discharged on — letting Agent 2 see them caused the
            # explanation text to invent treatments (e.g. "X-ray showed
            # your lungs were swollen", "methylprednisolone"). Agent 2
            # should reason only about the discharge diagnoses and the
            # discharge medication list; anything else is inpatient
            # context, not patient-facing discharge education.
            agent2_input = scope_for_agent2(
                extraction.model_copy(update={"procedures_performed": []})
            )
            agent2_result = await asyncio.to_thread(
                run_diagnosis_agent,
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
            if on_progress is not None:
                on_progress(3, "Medication", "Analyzing your medications...")
            # Harvest cross-section safety language (do-not-stop, stroke
            # signs, 911 callouts) from the full PDF text so Agent 3 can
            # reproduce warnings that live outside the medication list
            # itself. Empty string when nothing matches — handled inside
            # run_medication_agent as "no extra block".
            safety_ctx = _extract_safety_context(pdf_text)
            agent3_result = await asyncio.to_thread(
                run_medication_agent,
                extraction=scope_for_agent3(extraction),
                document_id=pdf_path,
                safety_context=safety_ctx,
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
            if on_progress is not None:
                on_progress(4, "Recovery", "Building your recovery plan...")
            agent4_result = await asyncio.to_thread(
                run_recovery_agent,
                extraction=scope_for_agent4(extraction),
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

    # ── Agent 5 — Escalation / warning-signs decision tree ──────────────────
    # Data contract: receives the full ExtractionOutput from Agent 1.
    # Returns dict with keys: text, fk_grade, passes.
    # Safety-critical — never let an Agent 5 exception crash the pipeline,
    # but record it as partial so the caller knows the decision tree is
    # missing from the response.
    escalation_guide = ""

    if agent1_succeeded:
        try:
            if on_progress is not None:
                on_progress(5, "Escalation", "Checking warning signs...")
            agent5_result = await asyncio.to_thread(
                run_escalation_agent,
                extraction=scope_for_agent5(extraction),
                document_id=pdf_path,
            )
            escalation_guide = agent5_result["text"]
            fk_scores["agent5"] = {
                "fk_grade": agent5_result["fk_grade"],
                "passes": agent5_result["passes"],
            }
            logger.info(
                "Agent 5 complete — FK grade: %.2f, passes: %s",
                agent5_result["fk_grade"],
                agent5_result["passes"],
            )
        except Exception as exc:
            logger.error("Agent 5 failed for %s: %s", pdf_path, exc)
            escalation_guide = ""
            pipeline_status = "partial"

    # ── Agent 6 — AI patient simulator (non-fatal) ──────────────────────────
    # Surfaces "missed concepts" — questions a confused patient would ask that
    # the document does not answer. Runs on every successful pipeline call.
    # Never fatal: run_patient_simulator_agent() returns a safe fallback on
    # all error paths so a simulator failure cannot degrade the pipeline status.
    patient_simulator_result = None
    if agent1_succeeded:
        try:
            if on_progress is not None:
                on_progress(6, "Simulator", "Running discharge quality check...")
            logger.info(
                "Agent 6 (patient simulator) starting for '%s'", pdf_path
            )
            patient_simulator_result = await asyncio.to_thread(
                run_patient_simulator_agent,
                extraction=extraction,
                document_id=pdf_path,
            )
            missed_n = sum(
                1
                for c in patient_simulator_result.missed_concepts
                if not c.answered_by_doc
            )
            logger.info(
                "Agent 6 complete: gap_score=%d missed=%d fk=%.1f",
                patient_simulator_result.overall_gap_score,
                missed_n,
                patient_simulator_result.fk_grade,
            )
        except Exception as exc:
            logger.error("Agent 6 failed for '%s': %s", pdf_path, exc)
            patient_simulator_result = None

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
        patient_simulator=patient_simulator_result,
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
        await _save_history_with_retries(
            database_url=database_url,
            session_id=db_session_id,
            document_hash=document_hash,
            extraction=extraction,
            fk_scores=fk_scores,
            pipeline_status=pipeline_status,
        )
        logger.info(
            "Discharge history saved — session: %s", db_session_id
        )
    except Exception as exc:
        logger.warning(
            "DB write failed (non-fatal) — session: %s — %s",
            db_session_id,
            exc,
        )

    return response
