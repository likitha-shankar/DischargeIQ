"""
File: dischargeiq/pipeline/orchestrator.py
Owner: Likitha Shankar
Description: Async coordinator for PDF→text extraction, Agents 1–5, optional Agent 6,
  and Neon history persistence - wraps each agent in try/except, scopes extraction per
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
from dischargeiq.agents.router_agent import run_router_agent
from dischargeiq.agents.escalation_agent import run_escalation_agent
from dischargeiq.agents.extraction_agent import run_extraction_agent
from dischargeiq.ingest import IngestResult, extract_document_text
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


# Trigger phrases for _extract_safety_context - matched case-insensitively
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
    pool=None,
) -> None:
    """
    Persist one discharge_history row with short retries for transient outages.

    When `pool` is provided (the long-lived lifespan pool from main.py), it is
    used directly and never closed here - the caller owns its lifecycle. When
    `pool` is None, a short-lived pool is created from `database_url` and closed
    after use (legacy / test path).

    Args:
        database_url: Database connection string from DATABASE_URL.
        session_id: Session identifier for the row.
        document_hash: SHA-256 hash of the source PDF.
        extraction: Agent 1 extraction payload.
        fk_scores: Aggregated FK score dict for agents 2-5.
        pipeline_status: Final pipeline status string.
        pool: Optional pre-existing asyncpg pool. When provided, avoids per-upload
              pool creation overhead (~100-200 ms per request).

    Raises:
        Exception: Re-raises the final persistence error after retries.
    """
    max_attempts = 3
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            if pool is not None:
                await save_discharge_history(
                    pool=pool,
                    session_id=session_id,
                    document_hash=document_hash,
                    extraction=extraction,
                    fk_scores=fk_scores,
                    pipeline_status=pipeline_status,
                )
            else:
                owned_pool = await get_db_pool(database_url)
                try:
                    await save_discharge_history(
                        pool=owned_pool,
                        session_id=session_id,
                        document_hash=document_hash,
                        extraction=extraction,
                        fk_scores=fk_scores,
                        pipeline_status=pipeline_status,
                    )
                finally:
                    await owned_pool.close()
            return
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
             - callers must treat an empty result as "no safety block"
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
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("safety context scan failed: %s", exc)
        return ""


async def run_pipeline(
    pdf_path: str,
    session_id: str | None = None,
    on_progress: Callable[[int, str, str], None] | None = None,
    document_hash: str | None = None,
    db_pool=None,
    raw_text: str | None = None,
) -> PipelineResponse:
    """
    Public entry point - wraps _run_pipeline_internal in a 300-second
    wall-clock timeout so a stuck LLM call cannot hang the API worker
    forever. On timeout, asyncio.TimeoutError is allowed to propagate;
    main.py translates it to an HTTP 504 for the client.

    Args:
        pdf_path:      Absolute path to a temporary PDF written by the API layer.
        session_id:    Optional session identifier propagated to the DB row.
        on_progress:   Optional callback fired after each agent completes.
        document_hash: SHA-256 hex digest of the PDF bytes, computed in main.py
                       from the in-memory upload before the tmpfile is written.
                       Avoids a second disk read inside the pipeline. When None,
                       the hash is computed from disk (legacy / test path).
        db_pool:       Optional long-lived asyncpg pool from main.py lifespan
                       context. When provided, avoids creating and closing a new
                       pool on every upload. When None, a short-lived pool is
                       created from DATABASE_URL (legacy / test path).
        raw_text:      Pre-extracted document text (mobile on-device OCR path,
                       POST /analyze/text). When set, pdf_path is a label only -
                       no file is read; router and Agent 1 consume this text.
    """
    return await asyncio.wait_for(
        _run_pipeline_internal(pdf_path, session_id, on_progress, document_hash, db_pool, raw_text),
        timeout=_PIPELINE_TIMEOUT_SECONDS,
    )


async def _run_pipeline_internal(
    pdf_path: str,
    session_id: str | None = None,
    on_progress: Callable[[int, str, str], None] | None = None,
    document_hash: str | None = None,
    db_pool=None,
    raw_text: str | None = None,
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

    Agents 2–5 are independent (all read Agent 1 output only) and run in
    parallel via asyncio.gather. return_exceptions=True means a failed agent
    comes back as an Exception object; each result is checked with isinstance
    so pipeline_status="partial" is set and empty string returned instead of
    passing an Exception where callers expect a dict.

    On any agent failure the pipeline sets pipeline_status="partial" and
    returns whatever was successfully extracted - it never raises to the
    caller (except for the wall-clock timeout enforced by run_pipeline).

    Args:
        pdf_path:      Absolute path to a temporary PDF written by the API layer.
        session_id:    Optional session identifier propagated to the DB row;
                       a fresh UUID is generated when omitted.
        document_hash: Pre-computed SHA-256 hex digest from main.py (avoids
                       re-reading the tmpfile). Falls back to disk read when None.

    Returns:
        PipelineResponse: Aggregated outputs. pipeline_status is "complete"
        when Agent 1 succeeds and no gaps were flagged; "complete_with_warnings"
        when only advisory completeness warnings fired; "partial" on any
        critical gap or downstream agent failure.
    """
    pipeline_start = time.monotonic()
    logger.info("Pipeline start - document: %s", pdf_path)

    # ── Router / Supervisor - document classification ────────────────────────
    # Classifies document type (heart_failure, copd, etc.) and gates obviously
    # non-discharge documents before any expensive agent calls run.
    # Always non-fatal: router failures fall back to should_process=True so a
    # real discharge summary is never silently dropped by a classifier error.
    router_result = {"should_process": True}
    # ── Ingest ONCE ─────────────────────────────────────────────────────────
    # The document text is read a single time here and shared by the router
    # and Agent 1. The previous flow parsed the PDF twice (router pre-read +
    # Agent 1 re-read) - pdfplumber costs 0.5-1.5s per parse, pure waste.
    # Ingest failure is non-fatal at this point: the router is skipped and
    # Agent 1's own failure path produces the standard "partial" stub.
    ingest_result: IngestResult | None = None
    if raw_text is not None:
        # Mobile OCR path: text was recognized on-device (ML Kit) and sent
        # via POST /analyze/text - there is no PDF to read. The scan-quality
        # note keeps a human in the loop on the lossier capture path.
        ingest_result = IngestResult(
            text=raw_text,
            source="ocr_photo",
            page_count=0,
            warnings=[
                "This summary was created from a phone camera scan. "
                "If something looks wrong, check the original paper document."
            ],
        )
    else:
        try:
            ingest_result = await asyncio.to_thread(extract_document_text, pdf_path)
        except Exception as exc:
            logger.error("Document ingest failed for %s: %s", pdf_path, exc)

    try:
        if on_progress is not None:
            on_progress(0, "Router", "Classifying document type...")
        if ingest_result is None:
            raise RuntimeError("no document text available for router")
        router_result = await asyncio.to_thread(run_router_agent, ingest_result.text)
        logger.info(
            "Router: type=%s confidence=%.2f should_process=%s",
            router_result["document_type"], router_result["confidence"], router_result["should_process"],
        )
    except Exception as exc:
        logger.warning("Router agent failed (non-fatal, continuing): %s", exc)

    if not router_result.get("should_process", True):
        logger.warning(
            "Router rejected document '%s': %s", pdf_path, router_result.get("reason", "")
        )
        # pipeline_status="rejected" is the FIRST-CLASS signal for "this is not
        # a discharge document" - both UIs branch on it to show a dedicated
        # try-another-document screen instead of empty results tabs. The
        # extraction_warnings entry is kept for logs and older clients.
        return PipelineResponse(
            extraction=ExtractionOutput(primary_diagnosis="Not a discharge document"),
            diagnosis_explanation="",
            medication_rationale="",
            recovery_trajectory="",
            escalation_guide="",
            fk_scores={},
            extraction_warnings=[
                f"Document rejected by router: {router_result.get('reason', 'Not a discharge summary')}"
            ],
            pipeline_status="rejected",
            rejection_reason=router_result.get("reason", "This does not look like a hospital discharge document."),
        )

    # ── Agent 1 - Extraction ─────────────────────────────────────────────────
    if on_progress is not None:
        on_progress(1, "Extraction", "Reading your discharge document...")
    # Produces the ExtractionOutput that all downstream agents consume.
    # On failure, fall back to a minimal stub so the API never returns 500.
    # pdf_text is initialised here (not inside try) so that downstream steps
    # - notably _extract_safety_context before Agent 3 - can reference it
    # unconditionally even if the text extraction step raised.
    pdf_text = ""
    try:
        # Each agent's LLM client (Anthropic / OpenAI / OpenRouter) is
        # synchronous and blocks the FastAPI event loop while waiting on the
        # network. With six sequential agents at 5–15 s each, that starves
        # the /progress poller in the loading iframe - the bar appears
        # frozen even though the pipeline is making progress. asyncio.to_thread
        # offloads each blocking call to the default thread pool so the
        # event loop can keep serving /progress in real time.
        # Text comes from the single ingest performed before the router -
        # a None ingest_result means that read failed, which is Agent 1's
        # standard failure path.
        if ingest_result is None:
            raise RuntimeError(f"document ingest failed for {pdf_path}")
        pdf_text = ingest_result.text
        extraction = await asyncio.to_thread(run_extraction_agent, pdf_text)
        # Surface ingest warnings (e.g. future OCR confidence banners) on the
        # same channel as extraction warnings so the UI needs no new wiring.
        if ingest_result.warnings:
            extraction.extraction_warnings.extend(ingest_result.warnings)
        pipeline_status = "complete"
        logger.info("Agent 1 complete - primary_diagnosis: '%s'", extraction.primary_diagnosis)
    except Exception as exc:
        logger.error("Agent 1 failed for %s: %s", pdf_path, exc)
        extraction = ExtractionOutput(
            primary_diagnosis="Extraction failed",
            extraction_warnings=[
                f"Agent 1 error - could not extract document: {type(exc).__name__}: {exc}"
            ],
        )
        pipeline_status = "partial"

    # Soonest follow-ups first - document order is not always chronological.
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
    #   critical  - primary_diagnosis / medications / red_flag_symptoms missing
    #               means this likely isn't a real discharge document, so we
    #               downgrade status to "partial".
    #   advisory  - common gaps on valid discharges (no follow-ups, missing
    #               patient name, etc.). We promote to "complete_with_warnings"
    #               so the UI can show a softer "Verified*" pill instead of
    #               the alarming amber "Incomplete" one.
    # Agent failures downstream (A2–A5) still set "partial" directly on their
    # own except path - a crashed agent is always a real failure.
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

    # Short label used as document_id in agent logs and FK CSV rows.
    # The full /tmp/... path was noisy and leaked ephemeral filenames.
    doc_id = os.path.basename(pdf_path)

    fk_scores: dict = {}
    diagnosis_explanation = ""
    medication_rationale = ""
    recovery_trajectory = ""
    escalation_guide = ""

    # ── Agents 2–5 - parallel ────────────────────────────────────────────────
    # All four are independent: each reads only Agent 1's ExtractionOutput.
    # asyncio.gather(return_exceptions=True) runs them concurrently in the
    # default thread pool (each is a blocking LLM call wrapped in to_thread).
    # Dropped wall-clock time: ~60s sequential → ~15s parallel at p95.
    #
    # IMPORTANT: return_exceptions=True means a failed agent returns an
    # Exception *object* in the results list rather than raising. Each result
    # is checked with isinstance before unpacking - passing an Exception where
    # downstream code expects a dict would be a silent data-corruption bug.
    #
    # FK log thread safety: log_fk_score() in utils/scorer.py holds
    # _fk_log_lock around CSV writes, so concurrent agents cannot interleave
    # header rows. Priority 3 (lock) was implemented before Priority 2
    # (parallelism) to avoid introducing the race inside a single upload.
    patient_simulator_result = None
    if agent1_succeeded:
        if on_progress is not None:
            on_progress(2, "Agents", "Analyzing your discharge summary...")

        # Harvest cross-section safety language once - shared by Agent 3.
        safety_ctx = _extract_safety_context(pdf_text)

        # Agent 2 input: strip inpatient-only procedures_performed so the
        # explanation doesn't invent in-hospital treatments as discharge advice.
        agent2_input = scope_for_agent2(
            extraction.model_copy(update={"procedures_performed": []})
        )

        # Per-agent progress: agents 2-6 run in parallel, so without this the
        # bar sat at step 2 for the whole burst and then leapt to the end -
        # the patient saw a frozen-then-jumping bar. Each completion advances
        # one step (2..6); completion ORDER is arbitrary, so the step number
        # is a count and the message names the agent that actually finished.
        _done_count = 1  # extraction already reported as step 1
        _count_lock = asyncio.Lock()

        async def _with_progress(label: str, message: str, fn, /, **kwargs):
            result = await asyncio.to_thread(fn, **kwargs)
            nonlocal _done_count
            async with _count_lock:
                _done_count += 1
                step = _done_count
            if on_progress is not None:
                on_progress(step, label, message)
            return result

        raw_results = await asyncio.gather(
            _with_progress(
                "Diagnosis", "Diagnosis explained in plain words...",
                run_diagnosis_agent,
                extraction=agent2_input,
                document_id=doc_id,
            ),
            _with_progress(
                "Medications", "Medications explained...",
                run_medication_agent,
                extraction=scope_for_agent3(extraction),
                document_id=doc_id,
                safety_context=safety_ctx,
            ),
            _with_progress(
                "Recovery", "Recovery plan ready...",
                run_recovery_agent,
                extraction=scope_for_agent4(extraction),
                document_id=doc_id,
            ),
            _with_progress(
                "Warning signs", "Warning signs organized...",
                run_escalation_agent,
                extraction=scope_for_agent5(extraction),
                document_id=doc_id,
            ),
            # Agent 6 only reads Agent 1's extraction, exactly like Agents
            # 2-5, so it joins the same parallel burst. It used to run
            # serially AFTER this gather - as the largest single call
            # (4096-token budget) that added 10-20s of pure wait to every
            # run. Its result is unpacked separately below because it
            # returns PatientSimulatorOutput, not an FK-scored text dict.
            _with_progress(
                "Quality check", "Running discharge quality check...",
                run_patient_simulator_agent,
                extraction=extraction,
                document_id=doc_id,
            ),
            return_exceptions=True,
        )

        # Agent 6 (last slot): non-fatal by contract - a failure here can
        # never degrade pipeline_status, matching the old serial behavior.
        simulator_raw = raw_results[4]
        if isinstance(simulator_raw, Exception):
            logger.error("Agent 6 failed for '%s': %s", pdf_path, simulator_raw)
        else:
            patient_simulator_result = simulator_raw
            logger.info(
                "Agent 6 complete: gap_score=%d missed=%d fk=%.1f",
                patient_simulator_result.overall_gap_score,
                sum(1 for c in patient_simulator_result.missed_concepts
                    if not c.answered_by_doc),
                patient_simulator_result.fk_grade,
            )

        _agent_labels = ["Agent 2", "Agent 3", "Agent 4", "Agent 5"]
        _fk_keys = ["agent2", "agent3", "agent4", "agent5"]
        _agent_results: list = []
        for i, result in enumerate(raw_results[:4]):
            if isinstance(result, Exception):
                logger.error(
                    "%s failed for %s: %s", _agent_labels[i], doc_id, result
                )
                _agent_results.append(None)
                pipeline_status = "partial"
            else:
                fk_scores[_fk_keys[i]] = {
                    "fk_grade": result["fk_grade"],
                    "passes": result["passes"],
                }
                logger.info(
                    "%s complete - FK grade: %.2f, passes: %s",
                    _agent_labels[i],
                    result["fk_grade"],
                    result["passes"],
                )
                _agent_results.append(result)

        diag_r, med_r, rec_r, esc_r = _agent_results
        diagnosis_explanation = diag_r["text"] if diag_r else ""
        medication_rationale = med_r["text"] if med_r else ""
        recovery_trajectory = rec_r["text"] if rec_r else ""
        escalation_guide = esc_r["text"] if esc_r else ""

    # Agent 6 (AI patient simulator) now runs inside the parallel gather
    # above - see the "Quality check" entry. patient_simulator_result was
    # unpacked there; None means Agent 1 failed or the simulator errored
    # (non-fatal by contract).

    elapsed = time.monotonic() - pipeline_start

    if pipeline_status == "partial":
        logger.warning(
            "Pipeline complete (partial) - %s - %.2fs", pdf_path, elapsed
        )
    else:
        logger.info(
            "Pipeline complete - %s - status: %s, %.2fs",
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
        # Router classification rides along for per-diagnosis media lookup
        # (GET /media/{document_type}) and analytics.
        document_type=router_result.get("document_type", "unknown"),
        patient_simulator=patient_simulator_result,
    )

    # ── DB write (non-fatal, background) ────────────────────────────────────
    # Persist one row per pipeline run so the history screen can list past
    # summaries. Runs as a fire-and-forget task: the row is bookkeeping the
    # patient never sees, and awaiting it inline meant a slow/down Neon added
    # its full retry ladder (1s+2s sleeps plus connection timeouts) to every
    # response. _persist_history_background swallows and logs all errors, so
    # the task can never surface an unhandled exception.
    db_session_id = session_id or str(uuid.uuid4())
    if document_hash is None:
        # Compute the fallback hash BEFORE returning - the tmpfile is deleted
        # by the API layer as soon as the response is sent, so the background
        # task cannot read it later. Legacy/test path only; API routes always
        # pass the hash in.
        try:
            if raw_text is not None:
                document_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
            else:
                with open(pdf_path, "rb") as pdf_file:
                    document_hash = hashlib.sha256(pdf_file.read()).hexdigest()
        except OSError as exc:
            logger.warning("Could not hash source for history row: %s", exc)
    if document_hash is not None:
        asyncio.create_task(_persist_history_background(
            session_id=db_session_id,
            document_hash=document_hash,
            extraction=extraction,
            fk_scores=fk_scores,
            pipeline_status=pipeline_status,
            pool=db_pool,
        ))

    return response


async def _persist_history_background(
    session_id: str,
    document_hash: str,
    extraction: ExtractionOutput,
    fk_scores: dict,
    pipeline_status: str,
    pool=None,
) -> None:
    """
    Background wrapper around _save_history_with_retries that can never raise.

    Runs as an asyncio task detached from the request so DB latency and
    outages never delay the pipeline response. All failures are logged and
    swallowed - history persistence is best-effort by design.

    Args: same as _save_history_with_retries, minus database_url (read from
    the environment here because the task outlives the request scope).
    """
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL not set")
        await _save_history_with_retries(
            database_url=database_url,
            session_id=session_id,
            document_hash=document_hash,
            extraction=extraction,
            fk_scores=fk_scores,
            pipeline_status=pipeline_status,
            pool=pool,
        )
        logger.info("Discharge history saved - session: %s", session_id)
    except Exception as exc:
        logger.warning(
            "DB write failed (non-fatal) - session: %s - %s", session_id, exc
        )
