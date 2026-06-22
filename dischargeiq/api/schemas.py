"""
api/schemas.py

Pydantic request and response models for the DischargeIQ HTTP API.

Kept separate from the domain models in dischargeiq/models/ so HTTP-layer
concerns (Optional fields, response shape) do not bleed into the pipeline
data contracts.
"""

from typing import Optional

from pydantic import BaseModel


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
