"""
Pipeline orchestrator for DischargeIQ.

Wires all five agents in sequence and aggregates their outputs into a
PipelineResponse. Full agent implementations are added in later tickets;
until then, run_pipeline returns a valid partial stub so POST /analyze
never crashes.

Depends on: dischargeiq.models.extraction, dischargeiq.models.pipeline.
"""

from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.models.pipeline import PipelineResponse


def run_pipeline(pdf_path: str) -> PipelineResponse:
    """
    Run the multi-agent discharge pipeline on a PDF file path.

    Args:
        pdf_path: Absolute path to a temporary PDF written by the API layer.

    Returns:
        PipelineResponse: Aggregated extraction and agent text outputs.
        Stub implementation uses pipeline_status "partial" until all agents
        are implemented.

    Note:
        Integration contract: when Agent 1 exists, pass pdf_path to the
        extraction agent and replace the stub ExtractionOutput below with
        validated model output. On any agent failure, still return a
        PipelineResponse with pipeline_status "partial" per project rules.
    """
    _ = pdf_path  # Reserved for pdfplumber / Agent 1 once DIS-5 lands

    extraction = ExtractionOutput(
        primary_diagnosis="(Not extracted yet)",
        extraction_warnings=[
            "Pipeline stub: agents are not fully implemented; "
            "this response is a placeholder."
        ],
    )

    return PipelineResponse(
        extraction=extraction,
        diagnosis_explanation="",
        medication_rationale="",
        recovery_trajectory="",
        escalation_guide="",
        fk_scores={},
        extraction_warnings=[],
        pipeline_status="partial",
    )
