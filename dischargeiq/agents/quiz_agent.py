"""
File: dischargeiq/agents/quiz_agent.py
Owner: Likitha Shankar
Description: Teach-back quiz generator (Sprint 3, Task 3.1) — turns Agent 1's
  extraction output into 5 non-leading multiple-choice questions across the five
  comprehension domains (diagnosis, medications, follow_up, activity, red_flags).
  The same frozen set is used for the pre and post phases so the comprehension
  delta measures the intervention, not question drift.
Key functions/classes: run_quiz_agent
Edge cases handled:
  - Malformed LLM JSON → ValueError with context (route maps to HTTP 502).
  - Questions failing schema validation are dropped; fewer than 3 surviving
    questions → ValueError (a 2-question quiz cannot measure comprehension).
  - Question text is FK-scored and logged like every other agent output.
Dependencies: dischargeiq.utils.llm_client, dischargeiq.utils.scorer,
  dischargeiq.models.quiz.
Called by: dischargeiq.api.routes.quiz (POST /quiz/generate).

Data contract (integration point):
  Input:  extraction dict — the `extraction` field of a PipelineResponse
          (ExtractionOutput.model_dump()). Missing/empty fields are fine; the
          prompt substitutes questions from richer domains.
  Output: QuizSet — validated questions, fk_grade, fk_passes.
"""

import json
import logging
import os
import re

from pydantic import ValidationError

from dischargeiq.models.quiz import QuizQuestion, QuizSet
from dischargeiq.utils.llm_client import (
    call_chat_with_fallback,
    get_llm_client,
    load_agent_prompt,
)
from dischargeiq.utils.scorer import fk_check, log_fk_score

logger = logging.getLogger(__name__)

# 5 questions × (stem + 4 options + explanation) fits well under this budget.
_MAX_TOKENS = 1500

# Below this count the quiz cannot meaningfully measure comprehension across
# domains — fail loudly instead of returning a 1-question "quiz".
_MIN_QUESTIONS = 3

# Extraction fields the quiz may draw from — everything else (names, dates,
# MRN) is trivia the prompt forbids, so it is not sent at all.
_QUIZ_FIELDS = (
    "primary_diagnosis",
    "secondary_diagnoses",
    "medications",
    "follow_up_appointments",
    "activity_restrictions",
    "dietary_restrictions",
    "red_flag_symptoms",
)


def run_quiz_agent(extraction: dict, session_id: str, document_id: str = "quiz") -> QuizSet:
    """
    Generate the frozen 5-question teach-back set for one discharge document.

    Sends only the quiz-relevant extraction fields to the LLM, parses the JSON
    array response, validates each question against the QuizQuestion schema
    (dropping invalid ones), and FK-scores the combined question text.

    Args:
        extraction: ExtractionOutput as a dict (PipelineResponse["extraction"]).
        session_id: Session the quiz belongs to (carried into the QuizSet).
        document_id: Source document label for FK logging.

    Returns:
        QuizSet: Validated questions with FK metadata.

    Raises:
        ValueError: If the LLM returns unparseable JSON or fewer than
                    _MIN_QUESTIONS valid questions survive validation.
    """
    quiz_input = {k: extraction.get(k) for k in _QUIZ_FIELDS if extraction.get(k)}
    if not quiz_input:
        raise ValueError(
            f"Quiz generation needs at least one populated extraction field "
            f"for session '{session_id}' — got none."
        )

    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    client, model = get_llm_client()
    system_prompt = load_agent_prompt("quiz_system_prompt.txt")
    user_message = (
        "Patient discharge data (JSON):\n\n"
        f"{json.dumps(quiz_input, indent=2)}\n\n"
        "Write the 5 teach-back questions."
    )

    raw = call_chat_with_fallback(
        client=client,
        model_name=model,
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=_MAX_TOKENS,
        provider=provider,
        agent_name="QuizAgent",
        document_id=document_id,
    )

    questions = _parse_questions(raw, session_id)
    if len(questions) < _MIN_QUESTIONS:
        raise ValueError(
            f"Quiz generation produced only {len(questions)} valid questions "
            f"for session '{session_id}' (minimum {_MIN_QUESTIONS})."
        )

    # FK gate — same rule as every agent: patient-facing text is scored and
    # logged. Quiz stems and options must be readable to be answerable.
    fk_text = " ".join(
        f"{q.question} {' '.join(q.options)} {q.explanation}" for q in questions
    )
    fk_result = fk_check(fk_text)
    log_fk_score(document_id, "quiz_agent", fk_result)
    if not fk_result["passes"]:
        logger.warning(
            "QuizAgent FK grade %.1f above threshold for '%s' — prompt needs revision",
            fk_result["fk_grade"], document_id,
        )

    return QuizSet(
        session_id=session_id,
        questions=questions,
        fk_grade=fk_result["fk_grade"],
        fk_passes=fk_result["passes"],
    )


def _parse_questions(raw: str, session_id: str) -> list[QuizQuestion]:
    """
    Parse the LLM response into validated QuizQuestion models.

    Strips accidental markdown fences, parses the JSON array, and validates
    each entry independently — one malformed question is dropped with a
    warning instead of discarding the whole set.

    Args:
        raw: Raw LLM response text.
        session_id: For log context only.

    Returns:
        list[QuizQuestion]: The questions that passed schema validation.

    Raises:
        ValueError: If the response is not a parseable JSON array.
    """
    cleaned = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"QuizAgent returned unparseable JSON for session '{session_id}': {exc}"
        ) from exc
    if not isinstance(parsed, list):
        raise ValueError(
            f"QuizAgent returned {type(parsed).__name__}, expected a JSON array "
            f"(session '{session_id}')."
        )

    questions: list[QuizQuestion] = []
    for i, item in enumerate(parsed):
        try:
            questions.append(QuizQuestion.model_validate(item))
        except ValidationError as exc:
            logger.warning(
                "QuizAgent question %d failed validation (session '%s') — dropped: %s",
                i, session_id, exc,
            )
    return questions
