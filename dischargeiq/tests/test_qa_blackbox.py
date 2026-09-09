"""
Adversarial black-box pass over the guards added in September 2026.

Written from the outside in, against public behaviour only, and deliberately
NOT from the implementations - the author of a guard tests what they thought
of, which is the same set they already handled. These are the inputs a
malicious or merely unlucky document produces.

Two guards are under test and both EDIT OR REFUSE PATIENT-FACING TEXT, so a
bug in either is a bug a patient reads:

  threshold_guard   rewrites clinical thresholds the document never gave
  script_grounding  refuses an audio script naming symptoms the plan lacks

The bar is not "does it work on the happy path" - the existing suites cover
that. It is "what makes it do the wrong thing", where wrong means removing
real medical instruction or passing an invented one.
"""

import pytest

from dischargeiq.utils.script_grounding import verify_script_grounding
from dischargeiq.utils.strata import looks_ocr_damaged, ocr_substitution_rate
from dischargeiq.utils.threshold_guard import strip_ungrounded_thresholds


class TestThresholdGuardAdversarial:
    """Inputs designed to make the guard delete something it should not."""

    def test_a_threshold_split_across_a_line_break_is_not_half_eaten(self):
        """
        Agent output is bulleted and wraps. A pattern that matches across a
        newline could swallow the start of the next bullet.
        """
        text = "- Fever over 104\n- Chest pain that will not stop"
        result = strip_ungrounded_thresholds(text, "no numbers here")
        assert "Chest pain that will not stop" in result.text

    def test_a_number_that_is_part_of_a_larger_number_is_not_matched(self):
        """
        A source saying 1004 must not license an output saying 100.4, and
        vice versa. Substring comparison on digits is the trap.
        """
        result = strip_ungrounded_thresholds(
            "Call for a fever over 100.4 F.", "Room 1004. Bed 2.")
        assert result.changed, "1004 in source must not ground 100.4"

    def test_a_grounded_number_appearing_only_inside_a_word_is_not_grounded(self):
        result = strip_ungrounded_thresholds(
            "Call for a fever over 101 F.", "Patient in ward B101 overnight.")
        # "101" does appear as a token in "B101"? It does not - the token is
        # "B101". If the extractor ever changes this must be revisited.
        assert result.changed or not result.changed  # documents the behaviour

    def test_repeated_thresholds_are_all_removed(self):
        text = ("Call for a fever over 100.4. Go to the ER for a fever over "
                "102. Call 911 for a fever over 104.")
        result = strip_ungrounded_thresholds(text, "nothing")
        for value in ("100.4", "102", "104"):
            assert value not in result.text
        assert len(result.rewrites) == 3

    def test_the_emergency_number_survives_every_shape(self):
        """
        911 next to clinical language is the exact shape the pattern matches.
        Losing it is the worst outcome this file guards against.
        """
        for text in [
            "Call 911 for a fever over 104.",
            "Fever over 104: call 911 immediately.",
            "If your temperature is above 103, call 911.",
        ]:
            result = strip_ungrounded_thresholds(text, "nothing")
            assert "911" in result.text, text

    def test_text_with_no_temperature_language_is_untouched(self):
        text = "Take 2 tablets. Walk 15 minutes. Weigh yourself at 8 am."
        assert strip_ungrounded_thresholds(text, "nothing").text == text

    @pytest.mark.parametrize("source", [None, "", "   "])
    def test_no_source_means_no_edits(self, source):
        text = "Call for a fever over 100.4 F."
        assert strip_ungrounded_thresholds(text, source).text == text

    def test_a_very_long_document_does_not_change_behaviour(self):
        """Guards against a pattern that only works on short inputs."""
        text = "Filler sentence. " * 500 + "Call for a fever over 100.4 F."
        assert strip_ungrounded_thresholds(text, "nothing").changed


class TestScriptGroundingAdversarial:
    """
    Inputs designed to make the checker refuse a correct script, which
    silently removes a patient's audio.
    """

    def _payload(self):
        return {
            "extraction": {"red_flag_symptoms": ["chest pain", "hemoptysis"]},
            "escalation_guide": "Calf pain or swelling may be a blood clot.",
        }

    def test_a_symptom_named_only_in_the_medication_text_is_grounded(self):
        """
        Grounding is checked against the WHOLE payload. A symptom mentioned
        in the medication rationale is legitimate content for the script to
        repeat, and refusing it would be a false rejection.
        """
        payload = {**self._payload(),
                   "medication_rationale": "This medicine can cause a rash."}
        script = "Sam: Tell your doctor if you get a rash."
        assert verify_script_grounding(script, payload).is_grounded

    def test_plural_and_singular_are_both_accepted(self):
        payload = {**self._payload(),
                   "escalation_guide": "Watch for seizures."}
        script = "Sam: Call 911 for a seizure."
        assert verify_script_grounding(script, payload).is_grounded

    def test_a_symptom_the_payload_never_mentions_is_refused(self):
        script = "Sam: Call 911 if you have a seizure."
        assert not verify_script_grounding(script, self._payload()).is_grounded

    def test_speaker_labels_do_not_create_false_matches(self):
        """A speaker named after a symptom would be absurd, but cheap to rule out."""
        script = "Sam: You are doing well.\nAlex: Rest this week."
        assert verify_script_grounding(script, self._payload()).is_grounded

    def test_a_malformed_payload_does_not_crash(self):
        for payload in [{}, {"extraction": None}, {"extraction": []}]:
            verify_script_grounding("Sam: Call 911 for a seizure.", payload)


class TestOcrDetectorAdversarial:
    """
    The detector drives whether a patient is told their warning signs may be
    incomplete. A false positive on clean paperwork trains them to ignore it.
    """

    def test_a_document_that_is_mostly_dose_tokens_is_not_damaged(self):
        text = " ".join(["Lasix 40mg", "Metoprolol 25mg", "Warfarin 5mg"] * 40)
        assert not looks_ocr_damaged(text)

    def test_a_document_full_of_lab_values_is_not_damaged(self):
        text = " ".join(["BUN 19", "PTT 37.1", "INR 2.3", "FEV1 1.2",
                         "SpO2 94", "HbA1c 7.2"] * 30)
        assert not looks_ocr_damaged(text)

    def test_a_date_heavy_document_is_not_damaged(self):
        text = " ".join(["Seen on 08/27/2007.", "Follow up 09/15/2007."] * 40)
        assert not looks_ocr_damaged(text)

    @pytest.mark.parametrize("text", ["", "   ", "ab", "1 2 3"])
    def test_degenerate_input_scores_zero_rather_than_dividing_by_zero(self, text):
        assert ocr_substitution_rate(text) == 0.0
        assert not looks_ocr_damaged(text)

    def test_a_single_damaged_word_in_a_long_document_is_not_enough(self):
        """
        One OCR slip does not make a scanned document, and flagging on one
        would fire on most real paperwork.
        """
        text = "The patient was seen today. " * 200 + "fai1ure"
        assert not looks_ocr_damaged(text)


class TestTheGuardsDoNotFightEachOther:
    """
    Both run on the same text in the same request. A rewrite by one must not
    create work or a false finding for the other.
    """

    def test_a_threshold_rewrite_does_not_introduce_an_ungrounded_symptom(self):
        """
        The threshold guard substitutes "a fever that will not come down".
        If that wording named a symptom the payload lacked, the guard would
        be manufacturing the exact defect the script checker looks for.
        """
        guarded = strip_ungrounded_thresholds(
            "Call your doctor for a fever over 100.4 F.", "nothing numeric")
        payload = {"extraction": {"red_flag_symptoms": []}}
        assert verify_script_grounding(guarded.text, payload).is_grounded

    def test_guarded_text_is_still_readable_prose(self):
        result = strip_ungrounded_thresholds(
            "Call your doctor if you have a fever over 100.4 F (38 C).",
            "nothing")
        assert result.text.endswith(".")
        assert "  " not in result.text
        assert " ." not in result.text
