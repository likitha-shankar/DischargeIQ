"""
api/routes/chat.py

POST /chat - grounded patient Q&A against their discharge document.

The route handler is thin: it validates the empty-message edge case, delegates
to ChatService (services/chat.py) for all domain work, and maps exceptions to
appropriate HTTP status codes. No business logic lives here.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from dischargeiq.api.middleware import has_valid_api_key
from dischargeiq.api.schemas import ChatRequest, ChatResponse
from dischargeiq.services.chat import chat_service
from dischargeiq.services.session import session_store

logger = logging.getLogger(__name__)

# NOT Bearer-gated, unlike every other LLM-cost route. The Streamlit chat panel
# runs in the patient's browser and calls this endpoint with fetch(), so a key
# handed to it would sit in page source for anyone to read - that is not a gate,
# it is a published key. Until the panel proxies its calls through the app
# server, the protection here is the per-IP rate limit (30/min) plus the rule
# below on where the grounding context may come from.
#
# That second protection used to be "a caller must supply a full
# pipeline_context", which was not a barrier at all: black-box testing on
# 15 Aug 2026 got a complete grounded answer from two hand-written fields and
# no key. Now an ANONYMOUS caller can only be answered from a session this
# server already analysed - and /analyze is gated - while an authenticated
# caller may still send its own context, which is what the mobile app needs
# when a session has been evicted.
#
# The expensive routes - /analyze, /analyze/text, /analyze/image (full 6-agent
# pipeline), /quiz/*, /media/case - ARE gated, and none of them is called from
# browser JavaScript, so gating them breaks nothing.
router = APIRouter()


def _resolve_context(request: ChatRequest, authenticated: bool) -> dict:
    """
    Return the pipeline context for a chat request.

    Priority: the server-side context cached by /analyze (normal path - the
    client sends only session_id), then the request's own pipeline_context
    (fallback for evicted sessions and older clients).

    The fallback is available only to an authenticated caller. Without that
    rule an anonymous caller could invent a discharge summary and have the
    model answer questions about it, which is free LLM spend on made-up
    clinical content wearing this project's name.

    Args:
        request:       The incoming ChatRequest.
        authenticated: Whether a valid API key accompanied the request.

    Returns:
        dict: PipelineResponse dict to ground the answer in.

    Raises:
        HTTPException 401: Anonymous caller supplied its own context.
        HTTPException 409: Neither source has context - the client must
            re-run /analyze (or re-send pipeline_context with a key).
    """
    context = session_store.get_context(request.session_id)
    if context is not None:
        return context
    if request.pipeline_context is not None:
        if authenticated:
            return request.pipeline_context
        raise HTTPException(
            status_code=401,
            detail="Supplying pipeline_context requires an API key. Analyze a "
                   "document first, then chat using that session id.",
        )
    raise HTTPException(
        status_code=409,
        detail="No discharge context for this session. Please analyze the "
               "document again.",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    authenticated: bool = Depends(has_valid_api_key),
):
    """
    Answer a patient question grounded in their discharge summary.

    Delegates all domain work to ChatService.answer() - prompt construction,
    LLM call, grounding detection, source attribution.

    Args:
        request: ChatRequest with message, session_id, and pipeline_context.

    Returns:
        ChatResponse: reply text, optional source_page, and from_document flag.

    Raises:
        HTTPException 500: When the LLM call fails or returns no choices.
    """
    if not request.message.strip():
        return ChatResponse(
            reply="Please type a question and I'll do my best to help.",
            source_page=None,
            from_document=False,
        )

    logger.info(
        "POST /chat - session: %s, message: %.60s…",
        request.session_id,
        request.message,
    )

    try:
        reply, source_page, from_document = chat_service.answer(
            message=request.message,
            pipeline_context=_resolve_context(request, authenticated),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Chat LLM call failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="The assistant is unavailable right now. Please try again.",
        )

    logger.info(
        "POST /chat response - session: %s, source_page: %s, length: %d, from_document: %s",
        request.session_id,
        source_page,
        len(reply),
        from_document,
    )

    return ChatResponse(reply=reply, source_page=source_page, from_document=from_document)


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    authenticated: bool = Depends(has_valid_api_key),
):
    """
    Stream a grounded answer as Server-Sent Events.

    Event protocol (one JSON object per `data:` line):
        {"delta": "<text fragment>"}   - repeated while the answer generates.
        {"done": true, "reply": ..., "source_page": ..., "from_document": ...}
                                       - final event; reply is the cleaned full
                                         text the client should keep.
        {"error": "<message>"}         - terminal event when the LLM fails.

    The LLM stream is a sync generator, so it runs via the threadpool
    StreamingResponse uses for sync iterators - the event loop is not blocked.

    Args:
        request: Same ChatRequest as POST /chat (pipeline_context optional).

    Raises:
        HTTPException 409: No context available for the session.
    """
    if not request.message.strip():
        empty = {"done": True, "reply": "Please type a question and I'll do my "
                 "best to help.", "source_page": None, "from_document": False}
        return StreamingResponse(
            iter([f"data: {json.dumps(empty)}\n\n"]), media_type="text/event-stream"
        )

    context = _resolve_context(request, authenticated)
    logger.info(
        "POST /chat/stream - session: %s, message: %.60s…",
        request.session_id, request.message,
    )

    def event_source():
        """Translate ChatService (kind, payload) tuples into SSE data lines."""
        try:
            for kind, payload in chat_service.answer_stream(
                message=request.message, pipeline_context=context
            ):
                if kind == "delta":
                    yield f"data: {json.dumps({'delta': payload})}\n\n"
                else:
                    yield f"data: {json.dumps({'done': True, **payload})}\n\n"
        except Exception as exc:
            logger.error("Chat stream failed: %s", exc)
            yield (
                "data: "
                + json.dumps({"error": "The assistant is unavailable right now. "
                              "Please try again."})
                + "\n\n"
            )

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        # Defeat proxy buffering (nginx fronts this app on Cloud Run) so
        # deltas reach the phone as they are generated, not in one flush.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
