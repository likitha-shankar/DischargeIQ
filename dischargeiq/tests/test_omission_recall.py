"""
Regression tests for the omission-recall checks in the corpus accuracy run.

Covers `scripts/corpus_accuracy_report.py`, which answers the question raised
as item 2.5 of the Dr. Leibowitz faculty review (25 Aug 2026): errors of
omission are the dominant failure mode and are invisible to the patient,
because a dropped medication or warning sign yields a clean, confident,
incorrect document.

These tests exist because the first implementation of that check was wrong in
a way that mattered. Run against the real corpus on 25 Aug 2026 it reported
six dropped warning signs; every one was a false positive:

  - "fevers" / "rashes" - the guide said "fever" and "rash". Plural mismatch.
  - "edema" - the guide said "swelling in arms or legs", which is a CORRECT
    plain-language translation and the entire purpose of the product. A metric
    that penalises successful rephrasing measures the opposite of the goal.
  - "fever greater than 100.5" - the guide said "fever over 100.5", flagged
    only because "greater" and "than" were counted as clinical content.

The opposite error matters more: a guide that substitutes its own threshold
("fever over 101" for a document that said 100.5) must NEVER score as covered,
because it reads as correct to the patient and is wrong for their case.
That is the case `test_substituted_threshold_is_caught` locks down.
"""

import sys
from pathlib import Path

import pytest

# The report generator is a script rather than a package module, so the
# scripts directory has to be importable before the functions can be reached.
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

from corpus_accuracy_report import (  # noqa: E402 - path set up above
    omitted_medications,
    omitted_red_flags,
)


def _output(*, flags=None, guide="", meds=None, rationale=""):
    """
    Build a minimal pipeline output for one assertion.

    Args:
        flags: Extracted red_flag_symptoms, if the test is about Agent 5.
        guide: The escalation_guide text those flags should appear in.
        meds: Extracted medications, if the test is about Agent 3.
        rationale: The medication_rationale text those drugs should appear in.

    Returns:
        A dict shaped like the fields of PipelineResponse the checks read.
    """
    return {
        "extraction": {
            "red_flag_symptoms": flags or [],
            "medications": [{"name": name} for name in (meds or [])],
        },
        "escalation_guide": guide,
        "medication_rationale": rationale,
    }


class TestRedFlagOmission:
    """Agent 5 is safety-critical, so its omissions are checked hardest."""

    @pytest.mark.parametrize(
        "symptom,guide",
        [
            ("fevers", "- fever over 101 degrees: you may have an infection."),
            ("rashes", "- rash that is spreading fast: see a doctor."),
            ("edema", "- swelling in arms or legs: fluid may be building up."),
            ("fever greater than 100.5", "- fever over 100.5: an infection."),
            ("temperature greater than 101.5", "- temperature over 101.5: call."),
        ],
    )
    def test_correct_rephrasing_is_not_an_omission(self, symptom, guide):
        """Plurals, plain-language swaps, and dropped filler must all pass."""
        assert omitted_red_flags(_output(flags=[symptom], guide=guide)) == []

    def test_genuinely_missing_symptom_is_reported(self):
        """A warning sign with no counterpart in the guide must be caught."""
        result = omitted_red_flags(
            _output(flags=["chest pain"], guide="- take your pills on time.")
        )
        assert result == ["chest pain"]

    def test_substituted_threshold_is_caught(self):
        """
        The most dangerous failure: right symptom, wrong number.

        The word "fever" alone must not be enough to mark this covered. A
        patient told to worry at 101 when their document said 100.5 has been
        given advice that reads correct and is wrong for them.
        """
        result = omitted_red_flags(
            _output(
                flags=["fever greater than 100.5"],
                guide="- fever over 101: you may have an infection.",
            )
        )
        assert result == ["fever greater than 100.5"]

    def test_no_guide_reports_nothing(self):
        """A failed Agent 5 is a pipeline error, not an omission finding."""
        assert omitted_red_flags(_output(flags=["chest pain"], guide="")) == []


class TestMedicationOmission:
    """A dropped drug is the review's own example of an invisible error."""

    def test_explained_medication_is_not_an_omission(self):
        """Dose and form may differ; the drug name is what must survive."""
        out = _output(
            meds=["Furosemide 40mg tablet"],
            rationale="Furosemide helps your body remove extra fluid.",
        )
        assert omitted_medications(out) == []

    def test_dropped_medication_is_reported(self):
        """Extracted but never explained is exactly the failure mode."""
        out = _output(
            meds=["Furosemide 40mg", "Metoprolol 25mg"],
            rationale="Furosemide helps your body remove extra fluid.",
        )
        assert omitted_medications(out) == ["Metoprolol 25mg"]

    def test_no_rationale_reports_nothing(self):
        """A failed Agent 3 is a pipeline error, not an omission finding."""
        assert omitted_medications(_output(meds=["Furosemide"], rationale="")) == []
