"""
api/routes/chat.py

POST /chat - grounded patient Q&A against their discharge document.

The route handler is thin: it validates the empty-message edge case, delegates
to ChatService (services/chat.py) for all domain work, and maps exceptions to
appropriate HTTP status codes. No business logic lives here.
"""

import logging

from fastapi import APIRouter, HTTPException

from dischargeiq.api.schemas import ChatRequest, ChatResponse
from dischargeiq.services.chat import chat_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
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
            pipeline_context=request.pipeline_context,
        )
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
