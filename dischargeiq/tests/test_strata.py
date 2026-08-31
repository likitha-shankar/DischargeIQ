"""
Tests for source-format stratification (Liebovitz review item 3.3).

Every accuracy figure this project quotes comes from 106 MTSamples documents,
which are all ONE format: dictated prose. Reporting per stratum is how you
find out whether extraction fails on faxes while looking fine overall.

Two findings are pinned here because both contradicted an initial assumption
and would otherwise be re-introduced:

1. Headings do NOT separate dictated from structured. Dictated medical
   transcription is full of "PROCEDURES:" and "HISTORY:" labels. A classifier
   built on headings filed 8 of 12 MTSamples documents as structured. BULLETS
   are the separator, measured at 0.0 per 100 lines for dictated against 62.8
   for structured.

2. OCR noise does NOT reliably identify scanned documents. Clean MTSamples
   scored 0.00 to 11.02; deliberately degraded copies scored 7.63 to 13.47.
   They overlap, because clinical dictation is full of lab values and
   abbreviations that look like OCR damage. So the scanned stratum comes from
   PROVENANCE - we built those files - not from inference.
"""

from pathlib import Path

import pytest

from dischargeiq.utils.strata import (
    Stratum,
    _bullet_score,
    classify_stratum,
    stratum_of_file,
)

_DICTATED = """DISCHARGE SUMMARY - Urology Discharge Summary
PROCEDURES:
Cystourethroscopy and transurethral resection of prostate.
ADMITTING DIAGNOSIS:
Difficulty voiding.
HISTORY:
This 67-year old patient was admitted because of enlarged prostate and
symptoms of bladder neck obstruction. Physical examination revealed normal
heart and lungs. Abdomen was negative for abnormal findings.
LABORATORY DATA:
BUN 19 and creatinine 1.1. Blood group was A, Rh positive, Hemoglobin 13.
COURSE IN THE HOSPITAL:
The patient tolerated the procedure well and was discharged in stable
condition with instructions to follow up in the office in two weeks.
"""

_STRUCTURED = """DISCHARGE SUMMARY
Patient Name: William R. Thompson
Discharge Date: 2026-03-27
PRIMARY DIAGNOSIS
Acute Decompensated Heart Failure (HFrEF)
SECONDARY DIAGNOSES
• Hypertension
• Type 2 Diabetes Mellitus
• Chronic kidney disease (Stage 2)
PROCEDURES PERFORMED
• Echocardiogram (2026-03-21): LVEF 35%
• IV Furosemide diuresis
DISCHARGE MEDICATIONS
• Furosemide 40mg once daily
• Metoprolol 25mg twice daily
"""


class TestBulletsAreTheSeparator:
    """Finding 1: headings are shared, bullets are not."""

    def test_dictated_prose_with_headings_is_dictated(self):
        """
        The case the first classifier got backwards.

        This text has six ALL-CAPS headings and would score as highly
        structured on a heading-based rule. It is a transcription.
        """
        assert classify_stratum(_DICTATED) is Stratum.DICTATED

    def test_bulleted_export_is_structured(self):
        assert classify_stratum(_STRUCTURED) is Stratum.STRUCTURED

    def test_the_measured_gap_is_real(self):
        """Dictated has no bullets at all; structured is full of them."""
        assert _bullet_score(_DICTATED) == 0.0
        assert _bullet_score(_STRUCTURED) > 30.0

    def test_headings_alone_do_not_make_a_document_structured(self):
        headings_only = "\n".join(
            ["ADMISSION DIAGNOSIS:", "Pneumonia.", "HISTORY:",
             "The patient presented with fever and cough for three days "
             "and was admitted for intravenous antibiotics and observation."] * 4
        )
        assert classify_stratum(headings_only) is Stratum.DICTATED


class TestProvenanceBeatsInference:
    """Finding 2: the scanned stratum is known, not detected."""

    @pytest.mark.parametrize("path,expected", [
        ("test-data/fax/mtsamples_001_fax.pdf", Stratum.SCANNED),
        ("test-data/mtsamples/mtsamples_001.pdf", Stratum.DICTATED),
        ("test-data/synthetic/heart_failure_01.pdf", Stratum.STRUCTURED),
    ])
    def test_known_directories_are_labelled_not_guessed(self, path, expected):
        """
        No file access needed and none should happen: the directory IS the
        answer. Inferring what we already know would only add a way to be
        wrong.
        """
        assert stratum_of_file(Path(path)) is expected

    def test_an_unreadable_file_is_unknown_not_a_crash(self):
        """Stratum is report metadata and must never break a corpus run."""
        assert stratum_of_file(Path("/nonexistent/whatever.pdf")) is Stratum.UNKNOWN


class TestHonestEdges:
    """UNKNOWN is a real answer, not a dumping ground."""

    @pytest.mark.parametrize("text", ["", "   ", "Too short to judge."])
    def test_short_text_is_unknown(self, text):
        assert classify_stratum(text) is Stratum.UNKNOWN

    def test_classification_never_raises_on_odd_input(self):
        for text in ["\x00" * 300, "•" * 300, "\n" * 300, "1234567890" * 40]:
            assert isinstance(classify_stratum(text), Stratum)
