"""
File: dischargeiq/ingest/reader.py
Owner: Likitha Shankar
Description: Single entry point for turning an uploaded document into text
  for Agent 1 (DIS-O1 increment 1). Today this is a thin wrapper around the
  proven pdfplumber digital path in extraction_agent; later increments add
  image-PDF detection and an OCR route behind the same function signature.
Used by: dischargeiq/pipeline/orchestrator.py
Dependencies: pdfplumber (page count), dischargeiq.agents.extraction_agent.
"""

import logging

import pdfplumber

# Integration point: the digital path delegates to the existing, battle-tested
# extractor. Its prepended anomaly notes (truncation, low scan quality) ride
# along inside IngestResult.text unchanged, so Agent 1 sees the exact same
# input it always has. Do not re-implement extraction logic here.
from dischargeiq.agents.extraction_agent import extract_text_from_pdf
from dischargeiq.ingest.models import IngestResult

logger = logging.getLogger(__name__)


def _count_pages(pdf_path: str) -> int:
    """
    Count pages in a PDF without extracting text.

    A failed count is never fatal: the count feeds metadata only, so any
    error degrades to 0 rather than blocking the pipeline (hard rule 7).

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        int: Page count, or 0 if the document could not be opened.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return len(pdf.pages)
    except (FileNotFoundError, OSError, ValueError) as exc:
        logger.warning("Page count failed for %s: %s", pdf_path, exc)
        return 0


def extract_document_text(pdf_path: str) -> IngestResult:
    """
    Extract text from an uploaded document via the appropriate ingest path.

    Increment 1 behavior: always the digital pdfplumber path. Detection of
    image-only/scanned PDFs and the OCR route are added in later increments
    behind this same signature, so callers never change.

    Args:
        pdf_path: Absolute or relative path to the uploaded PDF.

    Returns:
        IngestResult: text for Agent 1 plus ingest metadata. `source` is
        "digital_pdf", `ocr_confidence` is None, `warnings` is empty.

    Raises:
        FileNotFoundError: If the file does not exist at pdf_path.
        OSError: If the file cannot be opened (permissions / I/O).
        RuntimeError: For corrupted or password-protected PDFs — message is
            produced by extract_text_from_pdf and includes the path, so the
            orchestrator can set pipeline_status="partial" exactly as before.
    """
    text = extract_text_from_pdf(pdf_path)
    return IngestResult(
        text=text,
        source="digital_pdf",
        ocr_confidence=None,
        warnings=[],
        page_count=_count_pages(pdf_path),
    )
