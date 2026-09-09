"""
Patient-facing text is never silently empty.

Found by the launch review, 9 Sep 2026: eighteen test files touch Agent 5 and
NONE of them asserts that `escalation_guide` contains anything. A regression
that produced an empty escalation guide - the one output where acting on
nothing is dangerous - would have passed the entire suite.

That is the gap this file closes. It is deliberately dull: no clever inputs,
no edge cases. It asserts the single property that the rest of the suite
assumed and never checked.

WHY THE CORPUS DOES NOT COVER THIS. The corpus run measures readability and
grounding of text that EXISTS. An empty string has a fine reading grade and
invents nothing, so both gates pass it. Emptiness has to be asserted
separately or it is not asserted at all.
"""

import json
from pathlib import Path

import pytest

_OUTPUTS = Path(__file__).resolve().parents[2] / "evaluation" / "corpus_outputs"

#: The four sections a patient reads. Every one of these is the whole content
#: of a tab in the app - an empty one is a blank screen where advice should be.
_PATIENT_FACING = [
    "diagnosis_explanation",
    "medication_rationale",
    "recovery_trajectory",
    "escalation_guide",
]


def _completed_runs() -> list[tuple[str, dict]]:
    """Every corpus output that finished, as (name, payload)."""
    runs = []
    for path in sorted(_OUTPUTS.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if payload.get("pipeline_status") in ("complete", "complete_with_warnings"):
            runs.append((path.stem, payload))
    return runs


@pytest.fixture(scope="module")
def runs() -> list[tuple[str, dict]]:
    found = _completed_runs()
    if not found:
        pytest.skip("no corpus outputs present; run scripts/run_corpus_for_review.py")
    return found


class TestNoCompletedRunShipsAnEmptySection:
    """
    A run that reports `complete` is telling the patient every agent
    succeeded. If a section is empty, that claim is false.
    """

    @pytest.mark.parametrize("section", _PATIENT_FACING)
    def test_section_is_populated_on_every_completed_run(self, runs, section):
        empty = [name for name, payload in runs
                 if not (payload.get(section) or "").strip()]
        assert not empty, (
            f"{len(empty)} completed run(s) have an empty {section}: "
            f"{empty[:5]}. A status of complete promises this section exists."
        )

    def test_the_escalation_guide_is_never_empty(self, runs):
        """
        Called out separately from the parametrized case above, because this
        is the one where an empty section can hurt someone. A patient opening
        Warning Signs and finding nothing has been told, implicitly, that
        there is nothing to watch for.
        """
        empty = [name for name, payload in runs
                 if not (payload.get("escalation_guide") or "").strip()]
        assert not empty, f"empty escalation guide in: {empty}"


class TestTheEscalationGuideAlwaysCarriesEmergencyRouting:
    """
    Non-empty is necessary and not sufficient. Agent 5's contract is a
    three-tier decision tree, and the top tier is the one that matters.
    """

    def test_every_guide_names_the_emergency_number(self, runs):
        missing = [name for name, payload in runs
                   if "911" not in (payload.get("escalation_guide") or "")]
        assert not missing, (
            f"{len(missing)} guide(s) never mention 911: {missing[:5]}. "
            "Agent 5 is contractually required to emit all three tiers "
            "regardless of what the source document contained."
        )

    def test_every_guide_offers_more_than_one_level_of_urgency(self, runs):
        """
        A guide that only says "call 911" is as unusable as one that only says
        "call your doctor": the patient cannot tell the difference between
        situations. Two of the three tier headings must be present.
        """
        thin = []
        for name, payload in runs:
            guide = (payload.get("escalation_guide") or "").upper()
            tiers = sum(marker in guide for marker in
                        ("911", "ER TODAY", "CALL YOUR DOCTOR", "EMERGENCY"))
            if tiers < 2:
                thin.append(name)
        assert not thin, f"guide with fewer than two urgency levels: {thin[:5]}"


class TestAnEmptySectionWouldActuallyBeCaught:
    """
    Guards the guard. If the fixture silently found nothing, every test above
    would pass vacuously and this file would be decoration.
    """

    def test_the_corpus_actually_has_runs_to_check(self, runs):
        assert len(runs) >= 50, (
            f"only {len(runs)} completed runs found - the assertions above "
            "are weaker than they look"
        )

    def test_an_empty_string_would_fail_the_check(self):
        """The assertion logic itself, on a payload known to be bad."""
        bad = [("synthetic", {"escalation_guide": "   "})]
        empty = [n for n, p in bad if not (p.get("escalation_guide") or "").strip()]
        assert empty == ["synthetic"]
