"""
api/routes/quiz.py

Teach-back quiz endpoints (Sprint 3, Task 3.1):
    POST /quiz/generate - frozen 5-question set from the session's extraction
    POST /quiz/score    - score one phase (pre/post), persist, return delta

Route handlers are thin: generation delegates to the quiz agent, scoring to
services/quiz.py, persistence to db/quiz.py. Both endpoints are stateless with
respect to server memory (client carries the question set and grading key), so
they are safe under Cloud Run multi-instance routing.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from dischargeiq.agents.quiz_agent import run_quiz_agent
from dischargeiq.api.dependencies import get_db_pool
from dischargeiq.api.middleware import verify_api_key
from dischargeiq.api.schemas import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizScoreRequest,
    QuizScoreResponse,
)
from dischargeiq.db.quiz import get_latest_pre_percent, save_quiz_score
from dischargeiq.services.quiz import score_quiz
from dischargeiq.services.session import session_store
from dischargeiq.utils.audience import AUDIENCE_PATIENT

logger = logging.getLogger(__name__)
# verify_api_key is a no-op until DISCHARGEIQ_API_KEY is set; once set, both
# quiz endpoints (LLM cost + DB writes) require the same Bearer token as /analyze.
router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/quiz/generate", response_model=QuizGenerateResponse)
async def generate_quiz(request: QuizGenerateRequest):
    """
    Generate the frozen teach-back question set for a session.

    The client sends the extraction dict it already holds (same pattern as
    /chat's pipeline_context). The LLM call runs in a worker thread - the
    agent is synchronous like all other agents.

    Raises:
        HTTPException 422: Extraction has no quiz-relevant content.
        HTTPException 502: LLM returned unusable output after retries/failover.
    """
    logger.info("POST /quiz/generate - session: %s", request.session_id)

    # The client sends only the extraction, which has no age field, so the
    # addressee comes from the pipeline context /analyze cached for this
    # session. An evicted or unknown session falls back to the patient voice.
    context = session_store.get_context(request.session_id) or {}
    audience = context.get("audience", AUDIENCE_PATIENT)

    try:
        quiz_set = await asyncio.to_thread(
            run_quiz_agent,
            request.extraction,
            request.session_id,
            audience=audience,
        )
    except ValueError as exc:
        # Distinguish "nothing to quiz on" (client sent empty extraction)
        # from "LLM output unusable" (upstream failure).
        if "populated extraction field" in str(exc):
            raise HTTPException(status_code=422, detail=str(exc))
        logger.error("Quiz generation failed for '%s': %s", request.session_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Quiz generation is unavailable right now. Please try again.",
        )

    return QuizGenerateResponse(
        session_id=quiz_set.session_id,
        questions=quiz_set.questions,
        fk_grade=quiz_set.fk_grade,
    )


@router.post("/quiz/score", response_model=QuizScoreResponse)
async def score(request: QuizScoreRequest, pool=Depends(get_db_pool)):
    """
    Score one quiz phase and persist it (non-fatal without a database).

    For post phases, the comprehension delta is computed against the FIRST
    stored pre score for the session when the DB is available.

    Raises:
        HTTPException 422: answers/question_keys mismatch.
    """
    logger.info(
        "POST /quiz/score - session: %s, phase: %s", request.session_id, request.phase
    )
    try:
        result = score_quiz(
            session_id=request.session_id,
            phase=request.phase,
            question_keys=[k.model_dump() for k in request.question_keys],
            answers=request.answers,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    await save_quiz_score(pool, result)

    if request.phase == "post":
        pre_percent = await get_latest_pre_percent(pool, request.session_id)
        if pre_percent is not None:
            result.comprehension_delta = round(result.percent - pre_percent, 1)

    return QuizScoreResponse(**result.model_dump())
