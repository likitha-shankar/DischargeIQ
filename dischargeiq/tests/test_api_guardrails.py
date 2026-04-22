"""
API guardrail tests for upload validation and non-discharge detection.

Covers:
  - wrong file extension -> 415
  - wrong PDF magic bytes -> 415
  - oversized payload -> 413
  - critical extraction gaps produce non-discharge warning
"""

import pytest

from fastapi import HTTPException

from dischargeiq.main import _validate_uploaded_pdf
from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.utils.llm_client import require_provider_api_key
from dischargeiq.utils.warnings import assess_extraction_completeness


def test_require_provider_api_key_raises_valueerror_not_keyerror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing API key should surface a clear ValueError for operators."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        require_provider_api_key("anthropic")


def test_analyze_rejects_non_pdf_extension() -> None:
    """Validation helper raises 415 for non-PDF filenames."""
    with pytest.raises(HTTPException) as exc:
        _validate_uploaded_pdf("notes.docx", b"%PDF-pretend")
    assert exc.value.status_code == 415
    assert "Only PDF files are accepted" in str(exc.value.detail)


def test_analyze_rejects_bad_pdf_magic_bytes() -> None:
    """Validation helper raises 415 for renamed non-PDF content."""
    with pytest.raises(HTTPException) as exc:
        _validate_uploaded_pdf("looks_like_pdf.pdf", b"NOT_A_PDF")
    assert exc.value.status_code == 415
    assert "magic bytes missing" in str(exc.value.detail)


def test_analyze_rejects_oversized_pdf(monkeypatch) -> None:
    """Validation helper raises 413 when payload exceeds size cap."""
    monkeypatch.setattr("dischargeiq.main._MAX_FILE_SIZE_BYTES", 10)
    with pytest.raises(HTTPException) as exc:
        _validate_uploaded_pdf("big.pdf", b"%PDF-1234567890")
    assert exc.value.status_code == 413
    assert "File exceeds" in str(exc.value.detail)


def test_completeness_flags_likely_non_discharge_summary() -> None:
    """Critical extraction gaps include explicit non-discharge warning."""
    extraction = ExtractionOutput(
        primary_diagnosis="",
        medications=[],
        red_flag_symptoms=[],
        extraction_warnings=[],
    )
    result = assess_extraction_completeness(extraction)
    assert result["is_critical"] is True
    assert any(
        "may not be a hospital discharge summary" in warning.lower()
        for warning in result["critical_warnings"]
    )
