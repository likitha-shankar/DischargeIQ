"""
File: dischargeiq/ingest/models.py
Owner: Likitha Shankar
Description: Pydantic contract for the document ingest layer (DIS-O1). Every
  ingest path (digital PDF today, image OCR in later increments) returns an
  IngestResult so the orchestrator never needs to know which path ran.
Used by: dischargeiq/ingest/reader.py, dischargeiq/pipeline/orchestrator.py
Dependencies: pydantic v2 only — no LLM or PDF imports here by design.
"""

from typing import Literal, Optional

from pydantic import BaseModel


class IngestResult(BaseModel):
    """
    Output contract of the ingest layer.

    Data contract for downstream consumers (orchestrator → Agent 1):
        - `text` is always present and is the exact string Agent 1 consumes.
          It may be prefixed with plain-text anomaly notes (page truncation,
          low scan quality) produced by the underlying extractor.
        - `warnings` are patient-facing ingest warnings, surfaced as a UI
          banner. Empty list means a clean ingest. Never None.
        - `ocr_confidence` is None on the digital path; the OCR path (later
          increment) populates it with a 0.0–1.0 estimate.

    Attributes:
        text: Full extracted document text ready for Agent 1.
        source: Which ingest path produced the text.
        ocr_confidence: OCR confidence estimate, None for digital extraction.
        warnings: Human-readable ingest warnings for the UI banner.
        page_count: Number of pages in the source document (pre-truncation).
    """

    text: str
    source: Literal["digital_pdf", "ocr_image_pdf", "ocr_photo"]
    ocr_confidence: Optional[float] = None
    warnings: list[str] = []
    page_count: int = 0
