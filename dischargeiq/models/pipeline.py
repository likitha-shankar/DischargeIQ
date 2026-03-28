"""
Pydantic model for the full pipeline response.

Returned by POST /analyze after all five agents have run.
pipeline_status is "complete" when all agents succeed, or "partial" when
one or more agents failed with a fallback message.

Depends on: dischargeiq.models.extraction.
"""

from pydantic import BaseModel
from dischargeiq.models.extraction import ExtractionOutput


class PipelineResponse(BaseModel):
    """
    Aggregated output from all five DischargeIQ agents.

    Fields:
        extraction: Structured data from Agent 1.
        diagnosis_explanation: Plain-language diagnosis from Agent 2.
        medication_rationale: Per-drug explanation from Agent 3.
        recovery_trajectory: Week-by-week recovery guide from Agent 4.
        escalation_guide: Three-tier warning-sign decision tree from Agent 5.
        fk_scores: Flesch-Kincaid grade for each agent's text output.
        extraction_warnings: Completeness warnings from utils/warnings.py.
        pipeline_status: "complete" or "partial" — never raises unhandled exceptions.
    """

    extraction: ExtractionOutput
    diagnosis_explanation: str
    medication_rationale: str
    recovery_trajectory: str
    escalation_guide: str
    fk_scores: dict
    extraction_warnings: list
    pipeline_status: str  # "complete" or "partial"
