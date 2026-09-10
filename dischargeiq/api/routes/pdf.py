"""
api/routes/pdf.py

GET /pdf/{session_id}       - serve stored PDF bytes.
GET /simulator/{session_id} - serve Agent 6 JSON.

Both endpoints serve data that was stored during POST /analyze. They
exist to decouple the frontend from large payloads: the PDF is served
as raw bytes so the browser can render it in an <iframe> without a base64
data URI, and the simulator JSON is fetched separately to keep the /analyze
response lean.
"""

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from dischargeiq.services.session import session_store
from dischargeiq.utils.pdf_token import verify_pdf_token

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/pdf/{session_id}")
async def get_pdf(
    session_id: str,
    token: str | None = Query(None, description="Signed access token"),
    exp: str | None = Query(None, description="Token expiry, unix seconds"),
):
    """
    Return raw PDF bytes stored during POST /analyze.

    The frontend embeds the returned URL in an <iframe> so the browser can
    render the PDF natively without a large base64 data URI in the page.
    PDFs are held in an LRU-bounded in-memory store (cap: 50 sessions).

    Args:
        session_id: UUID returned by POST /analyze as pdf_session_id.

    Returns:
        Response: Raw PDF bytes with media_type application/pdf.

    Raises:
        HTTPException 404: When the session is unknown or has been evicted.
    """
    # The token, not the session id, is the credential. Verified live on
    # 9 Sep 2026: before this, the id alone returned 200 and a real patient's
    # 200 KB document to any caller.
    if not verify_pdf_token(session_id, token, exp):
        # 404, not 403. A distinct "forbidden" would confirm that this
        # session exists to someone guessing ids, and the two cases are the
        # same to a legitimate caller anyway.
        logger.warning("GET /pdf - rejected: missing or invalid access token")
        raise HTTPException(status_code=404, detail="PDF not found or expired.")

    pdf_bytes = session_store.get_pdf(session_id)
    if pdf_bytes is None:
        # The session id is a credential; keep it out of the logs.
        logger.warning("GET /pdf - not found or evicted")
        raise HTTPException(status_code=404, detail="PDF not found or expired.")
    logger.debug("GET /pdf - serving %d bytes", len(pdf_bytes))
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/simulator/{session_id}")
async def get_simulator(session_id: str):
    """
    Return Agent 6 (patient simulator) JSON for a prior /analyze session.

    Uses the same session_id as pdf_session_id / GET /pdf/{session_id}.

    Args:
        session_id: UUID returned by POST /analyze as pdf_session_id.

    Returns:
        dict: PatientSimulatorOutput.model_dump() from Agent 6.

    Raises:
        HTTPException 404: When no simulator output exists for this session.
    """
    payload = session_store.get_simulator(session_id)
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail="No simulator output for this session.",
        )
    return payload
