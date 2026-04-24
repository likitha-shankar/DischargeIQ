"""
Pydantic model for the full pipeline response.

Returned by POST /analyze after agents 1–5 have run; agent 6 may be present.
pipeline_status can be:
  - "complete" when all agents succeed and no warnings were raised
  - "complete_with_warnings" when all agents succeed but advisory/critical
    extraction warnings are present
  - "partial" when one or more agents fail and fallback text is used

Depends on: dischargeiq.models.extraction.
"""

from typing import Literal, Optional

from pydantic import BaseModel
from dischargeiq.models.extraction import ExtractionOutput


class MissedConcept(BaseModel):
    question: str
    answered_by_doc: bool
    gap_summary: str
    severity: Literal["critical", "moderate", "minor"]


class PatientSimulatorOutput(BaseModel):
    missed_concepts: list[MissedConcept]
    overall_gap_score: int
    simulator_summary: str
    fk_grade: float
    passes: bool


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
        pipeline_status: "complete", "complete_with_warnings", or "partial"
            — never raises unhandled exceptions.
    """

    extraction: ExtractionOutput
    diagnosis_explanation: str
    medication_rationale: str
    recovery_trajectory: str
    escalation_guide: str
    fk_scores: dict
    extraction_warnings: list
    pipeline_status: str  # "complete" | "complete_with_warnings" | "partial"
    patient_simulator: Optional[PatientSimulatorOutput] = None
