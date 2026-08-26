"""
Tests for dropping secondary diagnoses that restate the primary (Agent 1).

Secondary means OTHER conditions the patient also has. Restating the primary
makes a patient read one problem as two.

This is enforced in code rather than by the prompt because the prompt was
tried twice and did not hold. On 26 Aug 2026 a completeness-checklist rule,
then an explicit rule with a worked example placed beside the abbreviation
expansion that produces the duplicated string, both left 'Heart Failure with
Reduced Ejection Fraction' in secondary_diagnoses on the chf_narrative safety
profile. An instruction the model may or may not follow is not a guarantee.

The tests that matter most are in TestNeverDeletesARealDiagnosis. Removing a
duplicate is cosmetic; removing a real secondary diagnosis hides a condition
the patient has, which is far worse than the bug being fixed. Every case there
is a near-miss chosen to catch an over-eager rule.
"""

import pytest

from dischargeiq.agents.extraction_agent import _drop_primary_from_secondaries
from dischargeiq.models.extraction import ExtractionOutput


def _run(primary: str, secondaries: list[str]) -> list[str]:
    """Apply the dedup pass and return what survived."""
    extraction = ExtractionOutput(
        primary_diagnosis=primary,
        secondary_diagnoses=list(secondaries),
    )
    _drop_primary_from_secondaries(extraction)
    return extraction.secondary_diagnoses


class TestDropsRestatements:
    """A secondary adding no new clinical token is a duplicate."""

    @pytest.mark.parametrize("secondary", [
        "Heart Failure with Reduced Ejection Fraction",  # verbatim
        "HFrEF",                                          # abbreviation
        "heart failure",                                  # shortened
        "Reduced Ejection Fraction",                      # a fragment
        "Acute Heart Failure",                            # stopword added
    ])
    def test_restatement_of_primary_is_dropped(self, secondary):
        assert _run("Heart Failure with Reduced Ejection Fraction", [secondary]) == []

    def test_the_chf_narrative_case(self):
        """The exact failure from the 26 Aug safety run."""
        assert _run("Heart Failure with Reduced Ejection Fraction",
                    ["Heart Failure with Reduced Ejection Fraction"]) == []

    def test_expansion_matches_abbreviated_primary(self):
        """Direction does not matter; the tokens do."""
        assert _run("Type 2 Diabetes Mellitus", ["T2DM"]) == []

    def test_only_the_duplicate_is_removed(self):
        assert _run(
            "Acute Kidney Injury",
            ["AKI", "Chronic Kidney Disease", "Hypertension"],
        ) == ["Chronic Kidney Disease", "Hypertension"]


class TestNeverDeletesARealDiagnosis:
    """
    The failure mode that would make this fix worse than the bug.

    Leaving a duplicate is untidy. Deleting a genuine secondary diagnosis
    hides a condition the patient actually has, and nothing downstream would
    notice - Agents 2 to 5 only ever see what Agent 1 hands them.
    """

    def test_shared_token_is_not_enough(self):
        """
        "Pulmonary Hypertension" under a "Hypertension" primary must survive.

        It shares a token and even contains the primary as a substring, but it
        adds "pulmonary" and is a different disease. Any rule based on
        substring containment would delete it.
        """
        assert _run("Hypertension", ["Pulmonary Hypertension"]) == ["Pulmonary Hypertension"]

    def test_related_but_distinct_condition_survives(self):
        assert _run("Type 2 Diabetes Mellitus", ["Diabetic Neuropathy"]) == ["Diabetic Neuropathy"]

    def test_same_organ_different_disease_survives(self):
        assert _run("Chronic Kidney Disease", ["Acute Kidney Injury"]) == ["Acute Kidney Injury"]

    def test_unrelated_conditions_all_survive(self):
        secondaries = ["Hypertension", "GERD", "Osteoarthritis"]
        assert _run("Pneumonia", secondaries) == secondaries


class TestEdgeCases:
    """Nothing here may raise: this runs on every extraction."""

    def test_empty_secondaries(self):
        assert _run("Pneumonia", []) == []

    def test_blank_primary_leaves_secondaries_alone(self):
        """
        With no usable primary there is nothing to compare against, so the
        safe action is to change nothing rather than guess.
        """
        assert _run("...", ["Hypertension"]) == ["Hypertension"]

    def test_blank_secondary_entry_is_not_dropped(self):
        """An empty string has no tokens; it must not be treated as a match."""
        assert _run("Pneumonia", [""]) == [""]

    def test_punctuation_and_case_do_not_matter(self):
        assert _run("Heart Failure with Reduced Ejection Fraction",
                    ["HEART FAILURE, WITH REDUCED EJECTION FRACTION."]) == []
