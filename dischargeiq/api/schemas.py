"""
api/schemas.py

Pydantic request and response models for the DischargeIQ HTTP API.

Kept separate from the domain models in dischargeiq/models/ so HTTP-layer
concerns (Optional fields, response shape) do not bleed into the pipeline
data contracts.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from dischargeiq.models.quiz import QuizQuestion


class ChatRequest(BaseModel):
    """
    Request body for POST /chat.

    Fields:
        message:          The patient's plain-language question.
        session_id:       Browser session identifier (for future logging/history).
        pipeline_context: Full PipelineResponse dict so the LLM is grounded
                          in the patient's actual discharge data.
    """

    message: str
    session_id: str
    pipeline_context: dict


class ChatResponse(BaseModel):
    """
    Response body returned by POST /chat.

    Fields:
        reply:         Plain-language answer (target ≤ 80 words).
        source_page:   1-indexed page number referenced in the answer, or None.
        from_document: True when the reply is grounded in the patient's PDF.
                       The frontend uses this to decide whether to attribute
                       the answer to the document — never imply PDF sourcing
                       for general guidance (patient-trust requirement).
    """

    reply: str
    source_page: Optional[int] = None
    from_document: bool = True


class QuizGenerateRequest(BaseModel):
    """
    Request body for POST /quiz/generate.

    Fields:
        session_id: Client session identifier (same one used by /chat).
        extraction: The `extraction` field of the PipelineResponse the client
                    already holds. Sent by the client (like /chat's
                    pipeline_context) so quiz generation is stateless and safe
                    under Cloud Run multi-instance routing.
    """

    session_id: str
    extraction: dict


class QuizGenerateResponse(BaseModel):
    """Response body for POST /quiz/generate — the frozen question set."""

    session_id: str
    questions: list[QuizQuestion]
    fk_grade: float


class QuizQuestionKey(BaseModel):
    """Minimal grading key for one question (domain + correct option index)."""

    domain: str
    correct_index: int = Field(ge=0, le=3)


class QuizScoreRequest(BaseModel):
    """
    Request body for POST /quiz/score.

    The client sends back the grading key it received from /quiz/generate plus
    the patient's answers, in presentation order. answers uses -1 for skipped.
    Stateless by design — no server-side quiz storage required.
    """

    session_id: str
    phase: Literal["pre", "post"]
    question_keys: list[QuizQuestionKey] = Field(min_length=1, max_length=10)
    answers: list[int]


class QuizScoreResponse(BaseModel):
    """
    Response body for POST /quiz/score.

    comprehension_delta is populated only on post phases when a stored pre
    score exists (needs DATABASE_URL); otherwise the client computes the delta
    from the two scores it already has.
    """

    session_id: str
    phase: str
    score: int
    total: int
    percent: float
    domain_scores: dict[str, dict[str, int]]
    failed_domains: list[str]
    comprehension_delta: Optional[float] = None
