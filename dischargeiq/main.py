"""
DischargeIQ — FastAPI entry point.

Defines the REST API for the DischargeIQ multi-agent pipeline.
Endpoints:
  - GET  /health   → liveness + anthropic key flag + DB reachability (when configured)
  - POST /analyze  → accepts a discharge PDF, runs the agent pipeline
  - POST /chat     → accepts a patient question + pipeline context, returns
                     a grounded plain-language answer from the LLM

CORS is enabled for localhost Streamlit origins (ports 8501–8502) so the
floating chat widget can call /chat directly from the browser without a proxy.

Depends on: FastAPI, python-dotenv, dischargeiq.pipeline.orchestrator,
            dischargeiq.utils.llm_client, dischargeiq.utils.logger.
"""

import asyncio
import json
import logging
import os
import tempfile
import threading
import uuid
from collections import OrderedDict

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from dischargeiq.db.history import get_db_pool
from dischargeiq.pipeline.orchestrator import run_pipeline
from dischargeiq.utils.logger import configure_logging
from dischargeiq.utils.llm_client import get_llm_client

load_dotenv(dotenv_path=".env")
configure_logging()

logger = logging.getLogger(__name__)

# ── In-memory PDF store ───────────────────────────────────────────────────────
# Maps UUID session keys → raw PDF bytes. Capped at _PDF_STORE_MAX entries to
# avoid unbounded memory growth; oldest entry is evicted when the cap is reached.
# PDFs are stored here during /analyze and served via GET /pdf/{session_id}.
# This avoids large base64 data URIs in the Streamlit frontend.

_pdf_store: OrderedDict[str, bytes] = OrderedDict()
_simulator_store: OrderedDict[str, dict] = OrderedDict()
_PDF_STORE_MAX = 50

# ── /analyze upload limits ────────────────────────────────────────────────────
# 50MB is well above a real discharge PDF (rarely >5MB even with images) but
# low enough that a malicious upload can't exhaust the process memory.
# _PDF_MAGIC is the 4-byte prefix every real PDF file starts with — cheap
# sanity check that also blocks renamed binaries.
_MAX_FILE_SIZE_MB = 50
_MAX_FILE_SIZE_BYTES = _MAX_FILE_SIZE_MB * 1024 * 1024
_PDF_MAGIC = b"%PDF"
# Uvicorn serves endpoints from a thread pool; two concurrent /analyze
# calls can race on _pdf_store.popitem + assignment and corrupt the
# OrderedDict. All reads and writes go through this lock.
_pdf_store_lock = threading.Lock()


def _validate_uploaded_pdf(filename: str, contents: bytes) -> None:
    """
    Validate uploaded file metadata and bytes for /analyze.

    Args:
        filename: Original uploaded filename from the client.
        contents: Raw uploaded file bytes.

    Raises:
        HTTPException: 415 for non-PDF extension or invalid PDF signature.
        HTTPException: 413 when payload exceeds configured size cap.
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


def _store_pdf(pdf_bytes: bytes) -> str:
    """
    Store PDF bytes in the in-memory store under a new UUID key.

    Evicts the oldest entry when the store is at capacity to prevent unbounded
    memory growth. The returned key is the session identifier passed back to the
    frontend so it can request the PDF via GET /pdf/{session_id}.

    Args:
        pdf_bytes: Raw bytes of the uploaded PDF.

    Returns:
        str: UUID string identifying this PDF in the store.
    """
    session_id = str(uuid.uuid4())
    with _pdf_store_lock:
        if len(_pdf_store) >= _PDF_STORE_MAX:
            old_sid, _ = _pdf_store.popitem(last=False)  # evict oldest
            _simulator_store.pop(old_sid, None)
        _pdf_store[session_id] = pdf_bytes
    logger.debug("PDF stored — session_id: %s, size: %d bytes", session_id, len(pdf_bytes))
    return session_id


def _get_simulator_json(session_id: str) -> dict | None:
    """
    Look up serialized PatientSimulatorOutput for a pdf_session_id.

    Returns:
        dict | None: model_dump() from Agent 6, or None if missing.
    """
    with _pdf_store_lock:
        return _simulator_store.get(session_id)


def _get_pdf(session_id: str) -> bytes | None:
    """
    Look up PDF bytes previously stored under session_id.

    Args:
        session_id: UUID returned by _store_pdf().

    Returns:
        bytes | None: The stored PDF bytes, or None if the session was
        never stored or has been evicted from the LRU store.
    """
    with _pdf_store_lock:
        return _pdf_store.get(session_id)


app = FastAPI(
    title="DischargeIQ",
    description="Multi-agent AI system for plain-language patient discharge education",
    version="0.1.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# The Streamlit frontend (port 8501/8502) calls /chat directly from the browser
# via fetch(). Without CORS headers the browser will block the request.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://localhost:8502",
        "http://127.0.0.1:8501",
        "http://127.0.0.1:8502",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ── Request / response models for /chat ──────────────────────────────────────

class ChatRequest(BaseModel):
    """
    Request body for the POST /chat endpoint.

    Fields:
        message:          The patient's question text.
        session_id:       Browser session identifier (for future logging/history).
        pipeline_context: The full PipelineResponse dict so the LLM is grounded
                          in the patient's actual discharge data.
    """

    message: str
    session_id: str
    pipeline_context: dict


class ChatResponse(BaseModel):
    """
    Response body returned by POST /chat.

    Fields:
        reply:       Plain-language answer to the patient's question.
        source_page: Page number (1-indexed) referenced in the answer, or null.
    """

    reply: str
    source_page: Optional[int] = None


# ── System prompt for the /chat endpoint ─────────────────────────────────────
# This is injected as the LLM system role for every chat turn.
# Caps answer length at 80 words to keep responses readable at a glance.

_CHAT_SYSTEM_TEMPLATE = (
    "You are a warm, compassionate patient-education companion for "
    "DischargeIQ. You are talking with a real person who may be scared, "
    "confused, tired, or in pain after a hospital stay. Your job is to "
    "help them understand their discharge summary and to make them feel "
    "less alone.\n\n"

    "TONE — always:\n"
    "- Speak like a caring friend who happens to know their chart: warm, "
    "  unhurried, and reassuring.\n"
    "- If the patient shows worry or fear (e.g. 'is it bad?', 'I'm "
    "  scared', 'will I be okay?'), FIRST acknowledge the feeling in one "
    "  short sentence ('It's completely understandable to feel worried.'), "
    "  THEN give the factual answer from the summary, THEN close with "
    "  one gentle, honest reassurance grounded in what the document says "
    "  (e.g. their treatment plan, their follow-up appointments, or the "
    "  recovery trajectory).\n"
    "- Use 'you' and 'your'. Never lecture. Never sound like a chart.\n"
    "- Prefer plain, everyday words. Short sentences. 6th-grade reading "
    "  level. Target under 80 words unless the patient asks for more.\n\n"

    "WHAT YOU HAVE:\n"
    "Below is the patient's discharge summary — structured extraction "
    "fields plus a plain-language diagnosis_explanation paragraph. "
    "For questions like 'what is my diagnosis?', 'what does this mean?', "
    "'is it serious?', 'is it bad?', draw from diagnosis_explanation "
    "first. For medications, follow-up appointments, warning signs, "
    "activity restrictions, and dietary restrictions, draw from the "
    "extraction fields.\n\n"

    "WHEN TO REFUSE:\n"
    "Only refuse if the question is clearly outside the summary — for "
    "example a request for a second opinion, new medical advice, or "
    "information that simply is not in the document. In that case, say "
    "gently: 'I don't see that in your discharge summary — your doctor "
    "or care team is the best person to answer this one.' Never make up "
    "facts.\n\n"

    "SAFETY:\n"
    "- Never tell the patient to stop, skip, or change a medication. "
    "  If they ask about changing meds, direct them to their prescriber.\n"
    "- If they describe a red-flag symptom from the warnings list or an "
    "  emergency, tell them to call 911 or go to the nearest ER.\n\n"

    "DISCHARGE SUMMARY CONTEXT:\n{context_json}"
)


def _build_chat_system_prompt(pipeline_context: dict) -> str:
    """
    Construct the LLM system prompt for a /chat request.

    Serialises only the extraction fields — the agent text outputs are excluded
    to stay within token limits while keeping all clinically relevant data.

    Args:
        pipeline_context: Full PipelineResponse dict from the frontend.

    Returns:
        str: Formatted system prompt with embedded context JSON.
    """
    # Include the plain-language diagnosis explanation alongside the
    # structured extraction fields so the LLM can answer "what is my
    # diagnosis / what does this mean" questions directly. Other agent
    # outputs (medication_rationale, recovery_trajectory, escalation_guide)
    # are excluded to stay within the token budget — the extraction fields
    # already carry the structured medication/appointment/warning data.
    context_subset = {
        "extraction": pipeline_context.get("extraction", {}),
        "diagnosis_explanation": pipeline_context.get("diagnosis_explanation", ""),
        "pipeline_status": pipeline_context.get("pipeline_status", ""),
    }
    context_json = json.dumps(context_subset, indent=2, ensure_ascii=False)
    return _CHAT_SYSTEM_TEMPLATE.format(context_json=context_json)


def _extract_source_page(reply: str, pipeline_context: dict) -> Optional[int]:
    """
    Heuristically find the source page most relevant to this reply.

    Scans medications and follow-up appointments in the pipeline context for
    any name mentioned in the reply, then returns the source page of the first
    match. Returns None if no match is found.

    Args:
        reply:            The LLM's plain-language answer.
        pipeline_context: Full PipelineResponse dict.

    Returns:
        Optional[int]: 1-indexed page number, or None.
    """
    extraction = pipeline_context.get("extraction", {})
    reply_lower = reply.lower()

    for med in extraction.get("medications", []):
        name = (med.get("name") or "").lower()
        if name and name in reply_lower:
            source = med.get("source")
            if source and source.get("page"):
                return source["page"]

    for appt in extraction.get("follow_up_appointments", []):
        provider = (appt.get("provider") or "").lower()
        specialty = (appt.get("specialty") or "").lower()
        if (provider and provider in reply_lower) or (
            specialty and specialty in reply_lower
        ):
            source = appt.get("source")
            if source and source.get("page"):
                return source["page"]

    # Fall back to primary_diagnosis_source page if nothing more specific found.
    dx_source = extraction.get("primary_diagnosis_source")
    if dx_source and dx_source.get("page"):
        return dx_source["page"]

    return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """
    Liveness plus lightweight dependency signals for ops / eval prep.

    Returns 200 when the process is up. Includes whether ANTHROPIC_API_KEY is
    set (boolean only, never the secret) and whether DATABASE_URL, when set,
    can open a pool and run SELECT 1.
    """
    anthropic_set = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
    database_url = os.getenv("DATABASE_URL", "").strip()
    db_reachable: bool | None = None
    db_detail = ""
    if database_url:
        try:
            pool = await get_db_pool(database_url)
            try:
                async with pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                db_reachable = True
            finally:
                await pool.close()
        except Exception as exc:
            db_reachable = False
            db_detail = str(exc)[:300]
    else:
        db_detail = "DATABASE_URL not set"

    return {
        "status": "ok",
        "llm_provider": provider,
        "anthropic_api_key_configured": anthropic_set,
        "database": {
            "configured": bool(database_url),
            "reachable": db_reachable,
            "detail": db_detail,
        },
    }


@app.post("/analyze")
async def analyze_discharge(file: UploadFile = File(...)):
    """
    Accept a discharge PDF upload and run the multi-agent pipeline.

    Writes the uploaded file to a temp location and passes the path to
    run_pipeline(), which returns a PipelineResponse.

    Args:
        file: PDF file uploaded by the patient or clinician.

    Returns:
        dict: Serialised PipelineResponse (extraction, agent outputs, FK scores).

    Raises:
        HTTPException 413: If the uploaded file exceeds _MAX_FILE_SIZE_MB.
        HTTPException 415: If the filename is not .pdf or the bytes do not
                           start with the %PDF magic marker.
        HTTPException 500: If an unexpected error occurs during processing.
    """
    logger.info("POST /analyze received — filename: %s", file.filename)

    contents = await file.read()
    _validate_uploaded_pdf(file.filename, contents)

    # Store PDF bytes now so the frontend can fetch them via GET /pdf/{session_id}
    # without embedding a large base64 data URI in the page.
    pdf_session_id = _store_pdf(contents)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        result = await run_pipeline(tmp_path, session_id=pdf_session_id)
        logger.info(
            "POST /analyze complete — '%s', status: %s",
            file.filename,
            result.pipeline_status,
        )
        result_dict = result.model_dump()
        result_dict["pdf_session_id"] = pdf_session_id
        if result.patient_simulator is not None:
            with _pdf_store_lock:
                _simulator_store[pdf_session_id] = (
                    result.patient_simulator.model_dump()
                )
        return result_dict
    except asyncio.TimeoutError:
        # run_pipeline is wrapped in asyncio.wait_for(..., 300s). A timeout
        # here means an LLM call (or the full five-agent chain) got stuck
        # past the pipeline-wide budget. Surface as 504 so the UI can show
        # a "try a smaller PDF" message rather than a generic 500.
        logger.error("Pipeline timeout for document '%s'", file.filename)
        raise HTTPException(
            status_code=504,
            detail="Analysis took longer than 5 minutes. Please try a smaller or clearer PDF.",
        )
    except Exception as pipeline_error:
        logger.error(
            "Pipeline error for document '%s': %s", file.filename, pipeline_error
        )
        raise HTTPException(status_code=500, detail="Internal pipeline error.")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/pdf/{session_id}")
async def get_pdf(session_id: str):
    """
    Return the raw PDF bytes previously stored during /analyze.

    The frontend uses this URL in an <iframe> instead of a base64 data URI so
    large PDFs render correctly. PDFs are held in an in-memory OrderedDict
    capped at _PDF_STORE_MAX entries.

    Args:
        session_id: UUID returned by POST /analyze as 'pdf_session_id'.

    Returns:
        Response: Raw PDF bytes with media_type 'application/pdf'.

    Raises:
        HTTPException 404: If the session_id is unknown or has been evicted.
    """
    pdf_bytes = _get_pdf(session_id)
    if pdf_bytes is None:
        logger.warning("GET /pdf/%s — not found or evicted", session_id)
        raise HTTPException(status_code=404, detail="PDF not found or expired.")
    logger.debug("GET /pdf/%s — serving %d bytes", session_id, len(pdf_bytes))
    return Response(content=pdf_bytes, media_type="application/pdf")


@app.get("/simulator/{session_id}")
async def get_simulator(session_id: str):
    """
    Return Agent 6 (patient simulator) JSON for a prior /analyze session.

    Uses the same session id as pdf_session_id / GET /pdf/{session_id}.
    """
    payload = _get_simulator_json(session_id)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="No simulator output for this session",
        )
    return payload


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Answer a patient question grounded in their discharge summary.

    Builds a system prompt from the pipeline context, calls the configured
    LLM provider with the patient's message, and returns a plain-language
    response under 80 words.

    Args:
        request: ChatRequest with message, session_id, and pipeline_context.

    Returns:
        ChatResponse with reply text and optional source_page number.

    Raises:
        HTTPException 422: Pydantic validation failure (handled automatically).
        HTTPException 500: If the LLM call fails unexpectedly.
    """
    logger.info(
        "POST /chat — session: %s, message: %.60s…",
        request.session_id,
        request.message,
    )

    system_prompt = _build_chat_system_prompt(request.pipeline_context)

    try:
        client, model_name = get_llm_client()
        response = client.chat.completions.create(
            model=model_name,
            max_tokens=200,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message},
            ],
        )
    except Exception as llm_error:
        logger.error("Chat LLM call failed: %s", llm_error)
        raise HTTPException(
            status_code=500,
            detail="The assistant is unavailable right now. Please try again.",
        )

    content = response.choices[0].message.content
    reply = (content or "").strip()

    if not reply:
        reply = (
            "I could not find an answer in your discharge summary. "
            "Please ask your doctor."
        )

    source_page = _extract_source_page(reply, request.pipeline_context)

    logger.info(
        "POST /chat response — session: %s, source_page: %s, length: %d chars",
        request.session_id,
        source_page,
        len(reply),
    )

    return ChatResponse(reply=reply, source_page=source_page)
