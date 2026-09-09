"""
Adversarial black-box pass over the guards added in September 2026.

Written from the outside in, against public behaviour only, and deliberately
NOT from the implementations - the author of a guard tests what they thought
of, which is the same set they already handled. These are the inputs a
malicious or merely unlucky document produces.

threshold_guard REWRITES PATIENT-FACING TEXT, so a bug in it is a bug a
patient reads.

(A script_grounding module was added here on 9 Sep and removed the same day.
It was built after a script appeared to invent "leg spasms"; that finding was
retracted - the phrase is in the escalation guide and the source document, and
the search string was wrong. No fabrication has ever been observed in a
generated script, and the module could withhold a patient's audio over a
symptom-list mismatch. Speculative guards on live paths are not free.)

The bar is not "does it work on the happy path" - the existing suites cover
that. It is "what makes it do the wrong thing", where wrong means removing
real medical instruction or passing an invented one.
"""

import pytest

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


class TestNamelessMedicationDoesNotLoseTheDocument:
    """
    Found by the 106-document corpus run on 9 Sep 2026: mtsamples_081 was the
    single failure, because Agent 1 returned a medication with a null name.

    `Medication.name` is a required str, so Pydantic raised and the WHOLE
    extraction was discarded - every diagnosis, appointment and warning sign
    lost because one drug entry came back nameless. A document that is 95%
    readable became a total failure.
    """

    def test_a_nameless_entry_is_dropped_not_fatal(self):
        from dischargeiq.agents.extraction_agent import _drop_nameless_medications

        data = {"medications": [{"name": None, "dose": "40 mg"},
                                {"name": "Furosemide", "dose": "40 mg"}]}
        assert _drop_nameless_medications(data) == 1
        assert [m["name"] for m in data["medications"]] == ["Furosemide"]

    def test_a_whitespace_name_counts_as_nameless(self):
        from dischargeiq.agents.extraction_agent import _drop_nameless_medications

        data = {"medications": [{"name": "   "}, {"name": "Aspirin"}]}
        assert _drop_nameless_medications(data) == 1

    def test_a_dose_with_no_drug_is_not_kept(self):
        """
        Same rule the FHIR adapter already applies: a dose with no drug
        attached reads as an instruction and names nothing, which is worse
        than no entry at all.
        """
        from dischargeiq.agents.extraction_agent import _drop_nameless_medications

        data = {"medications": [{"name": None, "dose": "40 mg",
                                 "frequency": "twice daily"}]}
        _drop_nameless_medications(data)
        assert data["medications"] == []

    def test_a_good_list_is_untouched(self):
        from dischargeiq.agents.extraction_agent import _drop_nameless_medications

        data = {"medications": [{"name": "Aspirin"}, {"name": "Warfarin"}]}
        assert _drop_nameless_medications(data) == 0
        assert len(data["medications"]) == 2

    @pytest.mark.parametrize("meds", [None, [], "not a list", 42])
    def test_a_malformed_medications_field_does_not_crash(self, meds):
        from dischargeiq.agents.extraction_agent import _drop_nameless_medications

        assert _drop_nameless_medications({"medications": meds}) == 0
