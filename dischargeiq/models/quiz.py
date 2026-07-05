"""
File: dischargeiq/models/quiz.py
Owner: Likitha Shankar
Description: Pydantic domain models for the teach-back quiz loop (Sprint 3, Task 3.1) -
  question/option contracts produced by the quiz agent and score results returned by
  the scoring service. Shared by the API layer, Streamlit fallback UI, and Flutter app.
Key functions/classes: QuizQuestion, QuizSet, QuizScoreResult
Dependencies: pydantic v2 only.
Called by: dischargeiq.agents.quiz_agent, dischargeiq.api.routes.quiz, dischargeiq.db.quiz
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

# The five discharge comprehension domains from the measurement protocol
# (work plan §3a). Every quiz question is tagged with exactly one.
QuizDomain = Literal["diagnosis", "medications", "follow_up", "activity", "red_flags"]


class QuizQuestion(BaseModel):
    """
    One non-leading multiple-choice teach-back question.

    Data contract with the quiz agent: exactly 4 options, correct_index in 0–3,
    grounded ONLY in the patient's extracted discharge data - never general
    medical knowledge, so a wrong document produces wrong-looking questions a
    clinician can catch rather than silently plausible ones.
    """

    question: str
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    domain: QuizDomain
    # Shown AFTER the patient answers - one plain-language sentence explaining
    # the correct answer (used by the learning/mastery loop).
    explanation: str


class QuizSet(BaseModel):
    """
    The frozen question set for one document/session.

    The same set is used for the pre (baseline) and post (after intervention)
    phases - protocol §3a requires identical questions so the delta measures
    the intervention, not question difficulty.
    """

    session_id: str
    questions: list[QuizQuestion]
    fk_grade: float
    fk_passes: bool


class QuizScoreResult(BaseModel):
    """
    Score for one completed quiz phase.

    Fields:
        phase: "pre" (baseline, before reading DischargeIQ output) or "post".
        score / total: raw correct count over questions answered.
        percent: score/total as 0–100, rounded to one decimal.
        domain_scores: per-domain {"correct": n, "total": n} breakdown.
        failed_domains: domains with at least one wrong answer - the mastery
            path forces a focused review of these before re-testing.
        comprehension_delta: percent(post) - percent(pre) when this is a post
            phase and a stored pre score exists; None otherwise.
    """

    session_id: str
    phase: Literal["pre", "post"]
    score: int
    total: int
    percent: float
    domain_scores: dict[str, dict[str, int]]
    failed_domains: list[str]
    comprehension_delta: Optional[float] = None
