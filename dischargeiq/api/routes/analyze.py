"""
api/routes/analyze.py

POST /analyze      — discharge PDF upload → multi-agent pipeline.
POST /analyze/text — pre-extracted text (mobile on-device OCR) → same pipeline.

Validation logic (_validate_uploaded_pdf) is the only non-trivial code here.
Everything else delegates: PDF storage to SessionStore, pipeline execution to
run_pipeline() via the shared _execute_pipeline helper, progress callbacks to
SessionStore, and simulator storage to SessionStore after the pipeline completes.
"""

import asyncio
import hashlib
import logging
import os
import tempfile
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from dischargeiq.api.middleware import sanitize_for_log, verify_api_key
from dischargeiq.api.routes.progress import cleanup_progress_after_delay
from dischargeiq.api.schemas import AnalyzeTextRequest
from dischargeiq.pipeline.orchestrator import run_pipeline
from dischargeiq.services.session import session_store

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Upload limits ─────────────────────────────────────────────────────────────
# 50 MB is well above a real discharge PDF (rarely > 5 MB with images) but
# low enough that a malicious upload cannot exhaust process memory.
_MAX_FILE_SIZE_MB = 50
_MAX_FILE_SIZE_BYTES = _MAX_FILE_SIZE_MB * 1024 * 1024
_PDF_MAGIC = b"%PDF"


def validate_uploaded_pdf(filename: str, contents: bytes) -> None:
    """
    Validate uploaded file metadata and bytes for POST /analyze.

    Checks:
        1. Filename ends with .pdf (case-insensitive).
        2. Byte length does not exceed _MAX_FILE_SIZE_BYTES.
        3. First 4 bytes match the %PDF magic marker.

    Args:
        filename: Original uploaded filename from the client.
        contents: Raw uploaded file bytes.

    Raises:
        HTTPException 415: For non-PDF extension or invalid PDF signature.
        HTTPException 413: When payload exceeds the configured size cap.
    """
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are accepted.")
    if len(contents) > _MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {_MAX_FILE_SIZE_MB}MB limit.",
        )
    if not contents.startswith(_PDF_MAGIC):
        raise HTTPException(
            status_code=415,
            detail="File is not a valid PDF (magic bytes missing).",
        )


@router.post("/analyze", dependencies=[Depends(verify_api_key)])
async def analyze_discharge(request: Request, file: UploadFile = File(...)):
    """
    Accept a discharge PDF upload and run the multi-agent pipeline.

    Stores the PDF in memory for later retrieval via GET /pdf/{session_id},
    runs the 6-agent pipeline, and returns a serialised PipelineResponse.
    The pipeline runs inside asyncio.wait_for (300s) — a timeout is surfaced
    as HTTP 504 so the UI can suggest trying a smaller PDF.

    Args:
        request: FastAPI Request — used to access app.state.db_pool.
        file:    PDF file uploaded by the patient or clinician.

    Returns:
        dict: PipelineResponse plus pdf_session_id for /pdf and /simulator fetches.

    Raises:
        HTTPException 413: File exceeds 50 MB.
        HTTPException 415: Not a PDF or invalid PDF magic bytes.
        HTTPException 504: Pipeline timed out (> 5 minutes).
        HTTPException 500: Unexpected pipeline error.
    """
    # Sanitize filename before any logging — raw filenames can contain newlines,
    # ANSI escape codes, or path separators that corrupt log entries.
    safe_filename = sanitize_for_log(file.filename or "")
    logger.info("POST /analyze — filename: %s", safe_filename)

    contents = await file.read()
    validate_uploaded_pdf(file.filename, contents)

    # Hash computed over in-memory bytes — avoids a second disk read after
    # the pipeline writes the tmpfile and all agents have run.
    document_hash = hashlib.sha256(contents).hexdigest()

    # Session id is always server-generated. We accept the client hint only when:
    #   (a) it is a valid UUID format, AND
    #   (b) it does not already exist in the session store (prevents hijacking).
    # A client supplying a UUID that already maps to another user's data would
    # silently overwrite that session — that is a session-fixation attack.
    client_session_id = (request.headers.get("X-Discharge-Session-Id") or "").strip()
    try:
        proposed_id = str(uuid.UUID(client_session_id)) if client_session_id else None
    except ValueError:
        proposed_id = None

    if proposed_id and session_store.get_pdf(proposed_id) is not None:
        # Reject: would overwrite an existing session. Generate a fresh one.
        logger.warning(
            "POST /analyze — rejected X-Discharge-Session-Id %s: already in use",
            proposed_id,
        )
        proposed_id = None

    pdf_session_id = proposed_id or str(uuid.uuid4())

    session_store.set_progress(pdf_session_id, {
        "status": "running",
        "current_agent": 0,
        "agent_name": "Starting",
        "message": "Reading your document...",
    })
    session_store.store_pdf(contents, session_id=pdf_session_id)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    db_pool = getattr(request.app.state, "db_pool", None)

    try:
        return await _execute_pipeline(
            doc_label=safe_filename,
            pdf_session_id=pdf_session_id,
            pdf_path=tmp_path,
            document_hash=document_hash,
            db_pool=db_pool,
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── OCR text limits ───────────────────────────────────────────────────────────
# A one-page discharge summary is ~2–4k chars; 200k allows a very long
# multi-page scan while still bounding memory/token abuse. Below 100 chars a
# scan almost certainly failed — reject early with a clear message instead of
# burning 6 agent calls on noise.
_MIN_TEXT_CHARS = 100
_MAX_TEXT_CHARS = 200_000


@router.post("/analyze/text", dependencies=[Depends(verify_api_key)])
async def analyze_discharge_text(request: Request, body: AnalyzeTextRequest):
    """
    Run the multi-agent pipeline on pre-extracted document text.

    Sprint 2, Task 2.3 — the mobile OCR path: the phone recognizes text
    on-device (Google ML Kit) and sends ONLY the text, never the photo.
    That keeps images of paper documents off the wire and out of the
    backend entirely — a deliberate privacy property of the scan path.

    No PDF exists for this session, so GET /pdf/{session_id} will 404 —
    clients on the OCR path must not offer the "view original" affordance.

    Raises:
        HTTPException 422: Text too short (failed scan) or too long.
        HTTPException 504/500: Same semantics as POST /analyze.
    """
    text = body.text.strip()
    if len(text) < _MIN_TEXT_CHARS:
        raise HTTPException(
            status_code=422,
            detail="The scan captured too little text. Retake the photo with "
                   "the full page visible and good lighting.",
        )
    if len(text) > _MAX_TEXT_CHARS:
        raise HTTPException(status_code=422, detail="Scanned text is too long.")

    pdf_session_id = str(uuid.uuid4())
    logger.info(
        "POST /analyze/text — session: %s, chars: %d", pdf_session_id, len(text)
    )

    session_store.set_progress(pdf_session_id, {
        "status": "running",
        "current_agent": 0,
        "agent_name": "Starting",
        "message": "Reading your scanned document...",
    })

    return await _execute_pipeline(
        doc_label=f"ocr:{pdf_session_id}",
        pdf_session_id=pdf_session_id,
        pdf_path=f"ocr:{pdf_session_id}",  # label only — never opened
        document_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        db_pool=getattr(request.app.state, "db_pool", None),
        raw_text=text,
    )


async def _execute_pipeline(
    doc_label: str,
    pdf_session_id: str,
    pdf_path: str,
    document_hash: str,
    db_pool,
    raw_text: str | None = None,
) -> dict:
    """
    Shared pipeline execution for both analyze routes.

    Owns the progress lifecycle (running → complete/error → delayed cleanup),
    simulator storage, and the timeout/error → HTTP status mapping. Both
    routes delegate here so the two input paths cannot drift apart.

    Args:
        doc_label: Sanitized name for log lines (filename or ocr:<session>).
        pdf_session_id: Session id already registered with the progress store.
        pdf_path: Tmpfile path (PDF route) or a label (text route).
        document_hash: SHA-256 of the source bytes/text.
        db_pool: Long-lived pool from app.state, or None.
        raw_text: Pre-extracted text for the OCR path; None for PDFs.

    Returns:
        dict: Serialised PipelineResponse plus pdf_session_id.

    Raises:
        HTTPException 504: Pipeline wall-clock timeout.
        HTTPException 500: Any other pipeline error.
    """
    try:
        def update_progress(agent_num: int, agent_name: str, message: str) -> None:
            session_store.set_progress(pdf_session_id, {
                "status": "running",
                "current_agent": agent_num,
                "agent_name": agent_name,
                "message": message,
            })

        result = await run_pipeline(
            pdf_path,
            session_id=pdf_session_id,
            on_progress=update_progress,
            document_hash=document_hash,
            db_pool=db_pool,
            raw_text=raw_text,
        )

        session_store.set_progress(pdf_session_id, {
            "status": "complete",
            "current_agent": 7,
            "agent_name": "Complete",
            "message": "Almost ready...",
        })
        asyncio.create_task(cleanup_progress_after_delay(pdf_session_id))

        logger.info(
            "Analyze complete — '%s', status: %s", doc_label, result.pipeline_status
        )

        result_dict = result.model_dump()
        result_dict["pdf_session_id"] = pdf_session_id

        if result.patient_simulator is not None:
            session_store.store_simulator(
                pdf_session_id, result.patient_simulator.model_dump()
            )

        return result_dict

    except asyncio.TimeoutError:
        session_store.set_progress(pdf_session_id, {
            "status": "error",
            "current_agent": 0,
            "agent_name": "Timeout",
            "message": "Analysis timed out.",
        })
        asyncio.create_task(cleanup_progress_after_delay(pdf_session_id))
        logger.error("Pipeline timeout for document '%s'", doc_label)
        raise HTTPException(
            status_code=504,
            detail="Analysis took longer than 5 minutes. Please try a smaller or clearer PDF.",
        )
    except Exception as pipeline_error:
        session_store.set_progress(pdf_session_id, {
            "status": "error",
            "current_agent": 0,
            "agent_name": "Error",
            "message": "Analysis failed.",
        })
        asyncio.create_task(cleanup_progress_after_delay(pdf_session_id))
        logger.error("Pipeline error for '%s': %s", doc_label, pipeline_error)
        raise HTTPException(status_code=500, detail="Internal pipeline error.")
