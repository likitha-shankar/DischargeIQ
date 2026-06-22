"""
File: dischargeiq/tests/test_ingest.py
Owner: Likitha Shankar
Description: Unit tests for the ingest layer (DIS-O1 increment 1). Verifies
  the digital passthrough is byte-identical to the legacy extractor, the
  IngestResult contract holds, and error behavior matches the orchestrator's
  expectations (FileNotFoundError propagates, page-count failures degrade).
Run: python -m pytest dischargeiq/tests/test_ingest.py
Dependencies: a real synthetic PDF from test-data/ — no LLM calls, no network.
"""

from pathlib import Path

import pytest

from dischargeiq.agents.extraction_agent import extract_text_from_pdf
from dischargeiq.ingest import IngestResult, extract_document_text

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SAMPLE_PDF = _REPO_ROOT / "test-data" / "heart_failure_01.pdf"


@pytest.fixture(scope="module")
def sample_result() -> IngestResult:
    """Run ingest once on the heart failure sample and share the result."""
    return extract_document_text(str(_SAMPLE_PDF))


def test_digital_passthrough_text_identical(sample_result: IngestResult) -> None:
    """
    The ingest layer must not alter the digital path's output in any way.

    Agent 1's behavior is calibrated against extract_text_from_pdf output;
    a single changed character here would silently shift extraction quality.
    """
    legacy_text = extract_text_from_pdf(str(_SAMPLE_PDF))
    assert sample_result.text == legacy_text


def test_digital_result_contract(sample_result: IngestResult) -> None:
    """Digital path: source tag, no OCR confidence, no warnings, real pages."""
    assert sample_result.source == "digital_pdf"
    assert sample_result.ocr_confidence is None
    assert sample_result.warnings == []
    assert sample_result.page_count >= 1
    assert len(sample_result.text) > 100


def test_missing_file_raises_file_not_found() -> None:
    """
    A nonexistent path must raise FileNotFoundError, not return a result.

    The orchestrator's Agent 1 try/except depends on this exception to set
    pipeline_status="partial"; swallowing it would mask upload bugs.
    """
    with pytest.raises(FileNotFoundError):
        extract_document_text("/nonexistent/never_here.pdf")


def test_page_count_failure_degrades_to_zero(monkeypatch) -> None:
    """
    If page counting breaks after text extraction succeeded, ingest must
    still return the text (hard rule 7: never crash on metadata).
    """
    import dischargeiq.ingest.reader as reader

    class _BrokenPdfplumber:
        """Stub whose open() always fails, bound into reader's namespace only."""

        @staticmethod
        def open(path: str):
            raise OSError("simulated metadata failure")

    # Replace reader's module-level binding, NOT the shared pdfplumber module,
    # so extract_text_from_pdf (extraction_agent's own binding) still works.
    monkeypatch.setattr(reader, "pdfplumber", _BrokenPdfplumber)
    result = extract_document_text(str(_SAMPLE_PDF))
    assert result.page_count == 0
    assert len(result.text) > 100
