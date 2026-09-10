"""
The post-generation guard that removes clinical thresholds the patient's own
document never gave.

This is Dr Liebovitz's headline accuracy item and the first thing queued for
LOF clinician review: patient-facing output carrying "a fever over 100.4 F"
when the source said nothing of the kind. A threshold differs for an infant,
for an immunocompromised patient, and between surgeons - a number we supply
is a guess the patient reads as their own doctor's instruction.

Four prompt attempts failed to remove it. The measured reason is a split:
numerals written in a prompt DO get copied (removing them cut "10 pounds"
leakage from 5 of 10 documents to 3), but 100.4 F is the standard clinical
fever threshold and the model reaches for it whether or not any prompt
mentions it - it appears in Agent 5's output despite never appearing in
Agent 5's prompt. No wording removes a fact the model already knows.

Two properties, and the second matters more:

  Ungrounded thresholds are rewritten, or the guard does nothing.

  Grounded thresholds are NEVER touched. That number is the patient's own
  doctor speaking. Stripping it would replace real medical instruction with
  vaguer language, which is a worse defect than the one being fixed.

Measured on the corpus before wiring: 26 of 212 sections rewrote a threshold,
0 grounded thresholds stripped, 0 changes to any 911 instruction.
"""

import pytest

from dischargeiq.utils.threshold_guard import strip_ungrounded_thresholds


class TestUngroundedThresholdsAreRemoved:
    """The defect this exists for."""

    @pytest.mark.parametrize("text", [
        "Call your doctor if you have a fever over 100.4 F.",
        "Call your doctor for a temperature above 101.",
        "Go to the ER for a fever greater than 102 degrees F.",
        "Call if your temperature reaches 101.5 F.",
    ])
    def test_a_threshold_absent_from_the_source_is_rewritten(self, text):
        source = "Patient discharged in stable condition. Follow up in two weeks."
        result = strip_ungrounded_thresholds(text, source)
        assert result.changed
        assert "100.4" not in result.text
        assert "101" not in result.text
        assert "102" not in result.text

    def test_the_replacement_is_usable_advice_not_a_gap(self):
        """
        A deleted number would leave "a fever over ." in an escalation guide.
        The replacement is the wording the prompts' own GOOD examples use, so
        the patient reads something a clinician signed off on.
        """
        result = strip_ungrounded_thresholds(
            "Call your doctor if you have a fever over 100.4 F.",
            "No thresholds here.")
        assert "fever that will not come down" in result.text
        assert "  " not in result.text.replace("\n", " ")

    def test_a_celsius_equivalent_in_parentheses_goes_with_it(self):
        """
        "100.4 F (38 C)" is one threshold written twice. Stripping only the
        Fahrenheit value leaves the same invented number behind in the other
        unit.
        """
        result = strip_ungrounded_thresholds(
            "Call for a fever over 100.4 F (38 C).", "Nothing numeric.")
        assert "100.4" not in result.text
        assert "38" not in result.text

    def test_each_rewrite_is_reported(self):
        """The rate has to be measurable, not assumed."""
        result = strip_ungrounded_thresholds(
            "Fever over 100.4 F. Also call for a temperature above 102.",
            "No numbers.")
        assert len(result.rewrites) == 2
        assert {r.value for r in result.rewrites} == {"100.4", "102"}


class TestGroundedThresholdsAreNeverTouched:
    """
    The more important half. This is the patient's own doctor speaking.
    """

    def test_a_threshold_the_document_gives_survives_exactly(self):
        source = "Call the office for a temperature over 100.4 F."
        text = "Call your doctor if you have a fever over 100.4 F."
        result = strip_ungrounded_thresholds(text, source)
        assert not result.changed
        assert result.text == text

    def test_a_near_miss_is_not_treated_as_grounded(self):
        """
        A document saying 100 does not license an output saying 100.4. The
        numbers are compared as written for exactly this reason.
        """
        result = strip_ungrounded_thresholds(
            "Call for a fever over 100.4 F.",
            "Temperature was 100 on admission.")
        assert result.changed

    def test_a_grounded_and_an_ungrounded_threshold_in_one_text(self):
        source = "Call the office for a fever over 101."
        result = strip_ungrounded_thresholds(
            "Call for a fever over 101. Go to the ER for a temperature above 103.",
            source)
        assert "101" in result.text
        assert "103" not in result.text
        assert len(result.rewrites) == 1


class TestWhatMustNeverBeStripped:
    """Damage this guard could do if it were careless."""

    def test_911_is_untouchable(self):
        """
        The emergency number is the single most important token in the
        escalation guide. It is a three-digit number next to clinical
        language, which is exactly the shape this guard matches.
        """
        text = "CALL 911 IMMEDIATELY if you have a fever over 104."
        result = strip_ungrounded_thresholds(text, "No numbers.")
        assert "911" in result.text

    def test_week_numbers_and_small_integers_are_left_alone(self):
        text = "Week 2: rest. Take 1 tablet twice a day for 10 days."
        result = strip_ungrounded_thresholds(text, "Nothing.")
        assert result.text == text

    def test_a_dose_is_not_a_threshold(self):
        text = "Take Furosemide 40 mg once daily."
        result = strip_ungrounded_thresholds(text, "Nothing.")
        assert "40" in result.text

    def test_an_empty_source_changes_nothing(self):
        """
        No source means nothing can be established as grounded. Treating that
        as "strip everything" would rewrite an entire guide on the strength of
        a failed text extraction, hiding that failure behind vaguer wording.
        """
        text = "Call for a fever over 100.4 F."
        assert strip_ungrounded_thresholds(text, "").text == text
        assert strip_ungrounded_thresholds(text, None).text == text

    @pytest.mark.parametrize("text", ["", None])
    def test_empty_input_is_safe(self, text):
        assert strip_ungrounded_thresholds(text, "some source").text == text


class TestOnRealCorpusOutput:
    """
    Pins the measurement, so a future change to the pattern cannot quietly
    start stripping real medical instruction.
    """

    def test_a_real_leaked_line_is_caught(self):
        """Verbatim from mtsamples_019's escalation guide."""
        result = strip_ungrounded_thresholds(
            "- Fever over 101 F: Your body may be fighting an infection.",
            "Patient seen for follow up. No temperature threshold given.")
        assert result.changed
        assert "101" not in result.text

    def test_a_real_grounded_line_is_preserved(self):
        source = ("Return to the emergency department for increased "
                  "temperature greater than 101.5 or increased pain.")
        text = "- Temperature greater than 101.5: Call your surgeon today."
        result = strip_ungrounded_thresholds(text, source)
        assert not result.changed
        assert "101.5" in result.text


class TestDownwardThresholds:
    """
    Found 10 Sep 2026 by reviewing the six cases the grounding verifier still
    flagged on the corpus. The clause pattern matched only UPWARD comparators,
    so `mtsamples_038` shipped "Call your doctor if your temperature drops
    below 97 degrees Fahrenheit" - a fabricated hypothermia cutoff, past a
    guard built to catch exactly this.
    """

    def test_a_downward_threshold_is_rewritten(self):
        result = strip_ungrounded_thresholds(
            "Call your doctor if your temperature drops below 97 degrees Fahrenheit",
            "Patient afebrile throughout.")
        assert result.changed
        assert "97" not in result.text

    @pytest.mark.parametrize("clause", [
        "your temperature drops below 97 degrees Fahrenheit",
        "your temperature is below 95 degrees",
        "temperature falls below 96",
        "a temperature under 95 F",
        "temperature less than 95",
    ])
    def test_every_downward_phrasing_is_caught(self, clause):
        result = strip_ungrounded_thresholds(f"Call us if {clause}.", "No fever.")
        assert result.changed, f"missed: {clause}"

    def test_a_low_reading_is_not_described_as_a_fever(self):
        """
        The substantive risk in fixing this carelessly. One replacement for
        both directions would tell a hypothermic patient to watch for the
        opposite of their problem.
        """
        result = strip_ungrounded_thresholds(
            "Call if your temperature drops below 97 degrees", "No fever noted.")
        assert "fever" not in result.text.lower()
        assert "lower than normal" in result.text

    @pytest.mark.parametrize("sentence,expected", [
        ("Call if your temperature drops below 97 degrees",
         "Call if your temperature is lower than normal"),
        ("Call if you have a temperature below 95 degrees",
         "Call if you have a temperature that is lower than normal"),
    ])
    def test_the_result_is_still_a_readable_sentence(self, sentence, expected):
        """
        "over" is a preposition and "drops below" is a verb, so a single
        replacement produced "if your a temperature that is lower than
        normal". Correct in substance, unreadable on the page - and
        unreadable patient-facing text is its own defect.
        """
        assert strip_ungrounded_thresholds(sentence, "No fever.").text == expected

    def test_a_downward_threshold_the_document_gave_is_kept(self):
        """The patient's own doctor set it; it outranks us, in both directions."""
        source = "Call the clinic if your temperature drops below 96 F."
        result = strip_ungrounded_thresholds(
            "Call if your temperature drops below 96 degrees", source)
        assert not result.changed
        assert "96" in result.text


class TestTheDegreeSignParenthetical:
    """
    The module comment already claimed this case: "stripping only the
    Fahrenheit value would leave the Celsius one behind, which is the same
    defect in a different unit." The regex allowed `F` and `C` in the
    parenthetical but not `°`, so `(38 C)` was absorbed and `(38°C)` was not -
    and `mtsamples_032` shipped "a fever that will not come down (38°C)": the
    guard's own replacement text with a fabricated number still attached.
    """

    @pytest.mark.parametrize("clause", [
        "a fever over 100.4 F (38°C)",
        "a fever over 100.4 F (38 C)",
        "a fever over 100.4 F (38 degrees C)",
        "a fever over 100.4 F (38°)",
    ])
    def test_the_parenthetical_goes_with_the_clause(self, clause):
        result = strip_ungrounded_thresholds(clause, "Patient afebrile.")
        assert result.changed
        assert "38" not in result.text, f"left behind in: {result.text}"
        assert "100.4" not in result.text


class TestOrphanedUnitParentheticals:
    """
    mtsamples_032 shipped "a fever that will not come down (38°C)" - the
    guard's own replacement wording with a fabricated number still attached.
    The clause pass cannot catch it: by then there is no comparator left to
    match, and the model can also emit the phrase with a bare parenthetical
    and no comparator in the first place.
    """

    def test_an_orphan_after_our_own_phrase_is_removed(self):
        result = strip_ungrounded_thresholds(
            "Call your doctor if you have a fever that will not come down (38°C)",
            "Patient afebrile.")
        assert result.changed
        assert "38" not in result.text
        assert "a fever that will not come down" in result.text

    def test_it_fires_after_the_low_temperature_phrasings_too(self):
        for phrase in ("a temperature that is lower than normal",
                       "temperature is lower than normal"):
            result = strip_ungrounded_thresholds(f"Call if {phrase} (95 F).",
                                                 "No fever.")
            assert result.changed, phrase
            assert "95" not in result.text

    def test_a_grounded_parenthetical_is_left_alone(self):
        source = "Chart notes a reading of 38 C on admission."
        result = strip_ungrounded_thresholds(
            "a fever that will not come down (38 C)", source)
        assert not result.changed
        assert "38" in result.text

    @pytest.mark.parametrize("text", [
        "Rest for a while (2 weeks).",
        "Take your inhaler (the blue one).",
        "Walk each day (start slowly).",
        "Your dose is unchanged (see your list).",
    ])
    def test_ordinary_parentheticals_are_never_touched(self, text):
        """
        The rule only fires directly after a phrase this module inserted, on a
        parenthetical containing nothing but a number and a temperature unit.
        A guard that eats ordinary asides would be a worse defect than the one
        it fixes.
        """
        assert strip_ungrounded_thresholds(text, "No fever.").text == text

    def test_a_bare_parenthetical_elsewhere_is_not_touched(self):
        """Only ours. A number in parentheses after other prose is not our call."""
        text = "Your target weight (75 kg) is on your sheet."
        assert strip_ungrounded_thresholds(text, "No fever.").text == text
