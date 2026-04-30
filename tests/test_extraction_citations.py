"""
File: tests/test_extraction_citations.py
Owner: Likitha Shankar
Description: Black-box tests for source-span citation behaviour on the three scalar
  fields that previously always rendered ⚠️ — patient_name, discharge_date, and
  discharge_condition. Tests cover the icon-decision helper (_field_icon_status) and,
  as a slow live regression, Agent 1 against the hip_replacement_01.pdf test document.
Key functions/classes: test_source_spans_yield_checkmark_and_chip,
  test_value_without_source_yields_checkmark_no_chip,
  test_missing_value_yields_warning_icon,
  test_live_extraction_hip_replacement_has_source_page
Dependencies: dischargeiq.agents.extraction_agent, dischargeiq.models.extraction,
  streamlit_app._field_icon_status — import path relies on repo root in sys.path.
Called by: ``pytest tests/test_extraction_citations.py`` (fast, no LLM)
           ``pytest -m slow tests/test_extraction_citations.py`` (live LLM call)
"""

import os
import sys
from pathlib import Path

import pytest

# Make both the repo root (for ``tests`` imports) and the ``dischargeiq`` package
# importable when running this file directly or via pytest from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(_REPO_ROOT / ".env")

from dischargeiq.models.extraction import ExtractionOutput, SourceSpan
from streamlit_app import _field_icon_status


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source(page: int = 1, text: str = "Sample source text.") -> dict:
    """Return a source dict matching the SourceSpan wire format."""
    return {"page": page, "text": text}


def _make_full_extraction(**overrides) -> dict:
    """
    Return a minimal valid ExtractionOutput serialised as a dict.

    All three citation-target fields default to non-null values with source spans
    so that tests can selectively override individual fields.

    Args:
        **overrides: Field names and values to override in the returned dict.

    Returns:
        dict that mirrors what the Streamlit renderer receives from the API.
    """
    base = ExtractionOutput(
        patient_name="Jane Doe",
        patient_name_source=SourceSpan(page=1, text="Patient: Jane Doe DOB: 04/12/1952"),
        discharge_date="2024-03-15",
        discharge_date_source=SourceSpan(page=1, text="Date of Discharge: March 15, 2024"),
        primary_diagnosis="Heart Failure",
        primary_diagnosis_source=SourceSpan(page=1, text="Primary Diagnosis: Heart Failure"),
        discharge_condition="Stable",
        discharge_condition_source=SourceSpan(
            page=2, text="Patient discharged in stable condition."
        ),
    ).model_dump()

    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Test 1 — fully populated source spans produce ✅ + has_source=True
# ---------------------------------------------------------------------------

def test_source_spans_yield_checkmark_and_chip() -> None:
    """
    When all three citation fields have a populated SourceSpan the helper
    must return icon=✅ and has_source=True for each, indicating the renderer
    will show both the checkmark and a clickable 'Page N' chip.
    """
    ext = _make_full_extraction()

    for field_name, source_key in [
        ("patient_name", "patient_name_source"),
        ("discharge_date", "discharge_date_source"),
        ("discharge_condition", "discharge_condition_source"),
    ]:
        icon, has_source, _ = _field_icon_status(
            ext.get(field_name), ext.get(source_key)
        )
        assert icon == "✅", (
            f"{field_name}: expected ✅ with source span, got {icon!r}"
        )
        assert has_source is True, (
            f"{field_name}: expected has_source=True with source span"
        )


# ---------------------------------------------------------------------------
# Test 2 — value present but source=None → ✅ checkmark, no chip (no warning)
# ---------------------------------------------------------------------------

def test_value_without_source_yields_checkmark_no_chip() -> None:
    """
    When a field has a value but no source span the helper must return ✅ and
    has_source=False. A present-but-uncited value must not show a warning icon —
    it should render the value cleanly without scaring the user.
    """
    # Build extraction with all three _source fields absent (None after model_dump)
    ext = ExtractionOutput(
        patient_name="Jane Doe",
        discharge_date="2024-03-15",
        primary_diagnosis="Heart Failure",
        discharge_condition="Stable",
    ).model_dump()

    for field_name, source_key in [
        ("patient_name", "patient_name_source"),
        ("discharge_date", "discharge_date_source"),
        ("discharge_condition", "discharge_condition_source"),
    ]:
        icon, has_source, _ = _field_icon_status(
            ext.get(field_name), ext.get(source_key)
        )
        assert icon == "✅", (
            f"{field_name}: expected ✅ for present-but-uncited value, got {icon!r}"
        )
        assert has_source is False, (
            f"{field_name}: expected has_source=False when source is None"
        )


# ---------------------------------------------------------------------------
# Test 3 — missing value (None) → ⚠️ warning icon
# ---------------------------------------------------------------------------

def test_missing_value_yields_warning_icon() -> None:
    """
    When patient_name is None the helper must return ⚠️ to signal that the
    value was not found in the document. Source being None too does not change
    the verdict — the absence of the value is the warning trigger.
    """
    icon, has_source, tooltip = _field_icon_status(None, None)

    assert icon == "⚠️", f"Expected ⚠️ for missing value, got {icon!r}"
    assert has_source is False
    assert "No value extracted" in tooltip


# ---------------------------------------------------------------------------
# Test 4 — live pipeline regression (slow, requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_live_extraction_hip_replacement_has_source_page() -> None:
    """
    End-to-end regression: Agent 1 must return a patient_name_source with an
    integer page >= 1 when run against the hip_replacement_01.pdf test document.

    This test calls the real LLM — run only with ``pytest -m slow`` and a valid
    ANTHROPIC_API_KEY in the environment.
    """
    from dischargeiq.agents.extraction_agent import (
        extract_text_from_pdf,
        run_extraction_agent,
    )

    pdf_path = _REPO_ROOT / "test-data" / "hip_replacement_01.pdf"
    assert pdf_path.exists(), f"Test PDF not found: {pdf_path}"

    pdf_text = extract_text_from_pdf(str(pdf_path))
    result: ExtractionOutput = run_extraction_agent(pdf_text)

    assert result.patient_name is not None, (
        "Agent 1 did not extract patient_name from hip_replacement_01.pdf"
    )
    assert result.patient_name_source is not None, (
        "Agent 1 returned no patient_name_source — prompt or schema change may be missing"
    )
    assert isinstance(result.patient_name_source.page, int), (
        f"patient_name_source.page must be int, got {type(result.patient_name_source.page)}"
    )
    assert result.patient_name_source.page >= 1, (
        f"patient_name_source.page must be >= 1, got {result.patient_name_source.page}"
    )
