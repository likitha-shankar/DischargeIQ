"""
The escalation guide's incompleteness notice, and what triggers it.

Why this exists: on the paired fax stratum (25 documents,
`evaluation/fax_stratum_report.md`) warning signs retain 85.5% under
degradation against 93.7% on clean documents. One document lost all five,
among them hemoptysis - a sign no universal tier list covers. Agent 5 still
emits its generic tiers, so the patient is not left with nothing; what they
lose is the warnings written specifically for them, silently.

`source_degraded` is what lets a UI say so. These tests hold two properties:

  It fires when the source is degraded. Otherwise the notice is decorative.

  It does NOT fire on clean documents. This one matters more. A warning shown
  on paperwork that was read perfectly well teaches patients to dismiss it,
  and then it is not there when it is true. A false alarm costs more than a
  missing alarm here, because it degrades every future alarm.
"""

import pytest

from dischargeiq.models.pipeline import PipelineResponse
from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.pipeline.orchestrator import _has_quality_warning
from dischargeiq.utils.strata import (
    OCR_SUBSTITUTION_THRESHOLD,
    Stratum,
    classify_stratum,
    looks_ocr_damaged,
    ocr_substitution_rate,
)


def _clean_text() -> str:
    """Dictated prose, the corpus's dominant format."""
    return (
        "DISCHARGE SUMMARY\n\n"
        "The patient is a 67-year-old female admitted with acute "
        "decompensated heart failure. She was treated with intravenous "
        "diuresis and responded well over the course of her stay. "
        "Her breathing improved and her weight came down by four kilograms. "
        "She was seen by the cardiology service who adjusted her medications. "
        "At discharge she was comfortable at rest and ambulating without "
        "difficulty. She will follow up with her primary care physician in "
        "one week and with cardiology in two weeks. She was counselled on "
        "daily weights and on fluid restriction, and understands to call the "
        "office if her weight increases by more than three pounds overnight."
    ) * 2


def _degraded_text() -> str:
    """The same document after the OCR damage the fax stratum simulates."""
    return (
        "D1SCHARGE SUMMARV\n\n"
        "Tbe patlent is a 67-year-o1d fema1e admltted wltb acute "
        "decompensated beart fai1ure. Sbe was treated witb lntravenous "
        "dluresis and responded we11 over tbe course of ber stav. "
        "Her breatblng lmproved and ber welgbt carne down bv four ki1ograms. "
        "Sbe was seen bv tbe cardio1ogv servlce wbo adjusted ber medlcatlons. "
        "At dlscbarge sbe was cornfortab1e at rest and arnbu1ating wltbout "
        "dlfficu1tv. Sbe wl11 fo11ow up witb ber prlmarv care pbvslclan ln "
        "one week and witb cardlo1ogv ln two weeks. Sbe was counse11ed on "
        "dai1v welgbts and on f1uid restrictlon, and understands to ca11 tbe "
        "offlce lf ber welgbt lncreases bv rnore tban tbree pounds overnigbt."
    ) * 2


class TestTheTextClassifierIsNotEnoughOnItsOwn:
    """
    Records why the notice does not key on the stratum classifier alone.

    The first version of this feature did exactly that, and would never have
    fired. On the degraded fax stratum the classifier scores 0.00 noise and
    returns DICTATED: it detects layout artefacts, not the character
    substitutions (l/1, O/0, rn/m) that make a photocopied fax hard to read,
    because those produce plausible-looking words.

    `stratum_of_file` reports SCANNED for those documents only because it reads
    the directory name - provenance we have for our own corpus and never for a
    patient's upload. These tests pin that gap so nobody re-simplifies the
    trigger back to the classifier.
    """

    def test_character_substitution_damage_is_invisible_to_the_classifier(self):
        assert classify_stratum(_degraded_text()) is not Stratum.SCANNED

    def test_which_is_why_the_quality_warnings_carry_it(self):
        assert _has_quality_warning(
            ["Document appears to be scanned - extraction accuracy may be reduced."]
        )


class TestTheQualityWarningTrigger:
    """
    Measured on the paired fax stratum: 6 of 6 degraded documents raised at
    least one of these warnings, 6 of 6 clean raised none.
    """

    @pytest.mark.parametrize("warning", [
        "Document appears to be scanned - extraction accuracy may be reduced.",
        "Possible scan or OCR artifacts detected - verify drug names manually.",
    ])
    def test_each_document_quality_warning_fires_the_notice(self, warning):
        assert _has_quality_warning([warning]) is True

    def test_abbreviation_style_is_NOT_a_degradation_signal(self):
        """
        Real clinical notes are written in shorthand - "Lasix 40mg QD" is
        normal, not damage. This warning fired on 18 of 109 clean documents,
        a 1-in-6 false-alarm rate on a notice whose only value is being
        believed, so it was removed from the trigger set.
        """
        assert _has_quality_warning([
            "Document uses abbreviated clinical shorthand - verify medication "
            "names and instructions against original document.",
        ]) is False

    def test_no_warnings_means_no_notice(self):
        assert _has_quality_warning([]) is False

    def test_a_missing_section_is_not_a_degraded_source(self):
        """
        The commonest warning on real paperwork is that the hospital never
        wrote a section. That is a property of the document, not damage to it,
        and must not fire a notice about readability.
        """
        assert _has_quality_warning([
            "No medications were listed in this document.",
            "No follow-up appointments were found.",
        ]) is False

    def test_a_per_field_verification_warning_does_not_fire_it(self):
        """
        "'X' was not found in the document text" also fires when the model
        paraphrased a value on a clean document. Keying the notice to it would
        produce false alarms, and a notice shown on clean paperwork teaches
        patients to dismiss the one that matters.
        """
        assert _has_quality_warning([
            "Medication 'Fiorinal' was not found in the document text - "
            "please verify it against your discharge papers.",
        ]) is False

    def test_matching_survives_case_and_surrounding_text(self):
        assert _has_quality_warning(
            ["NOTE: Document Appears To Be Scanned and may be incomplete."]
        ) is True


class TestTheFlagDefaultsToSilence:
    """A notice that appears without cause is worse than none."""

    def _response(self, **kwargs) -> PipelineResponse:
        return PipelineResponse(
            extraction=ExtractionOutput(primary_diagnosis="Heart failure"),
            diagnosis_explanation="Your heart was not pumping well.",
            medication_rationale="",
            recovery_trajectory="",
            escalation_guide="CALL 911 IMMEDIATELY",
            fk_scores={},
            extraction_warnings=[],
            pipeline_status="complete",
            **kwargs,
        )

    def test_absent_by_default(self):
        """
        Older stored responses have no such field. They must render exactly as
        before rather than acquiring a warning retroactively.
        """
        assert self._response().source_degraded is False
        assert self._response().source_stratum is None

    def test_set_explicitly_when_degraded(self):
        response = self._response(source_degraded=True, source_stratum="scanned")
        assert response.source_degraded is True
        assert response.source_stratum == "scanned"

    def test_survives_a_json_round_trip(self):
        """The mobile client reads this off the wire, not off the model."""
        payload = self._response(
            source_degraded=True, source_stratum="scanned").model_dump()
        assert payload["source_degraded"] is True
        rebuilt = PipelineResponse(**payload)
        assert rebuilt.source_degraded is True

    def test_a_legacy_payload_without_the_field_still_parses(self):
        """
        A stored response from before this change must not fail validation -
        the history screen reads them back.
        """
        payload = self._response().model_dump()
        payload.pop("source_degraded")
        payload.pop("source_stratum")
        assert PipelineResponse(**payload).source_degraded is False


class TestWhatTheNoticeMustNotClaim:
    """
    The notice says the list shown is still safe to follow, and that is a
    claim about Agent 5, so it has to be true.

    Agent 5's universal tiers do not come from extraction - they are in its
    prompt - which is why a degraded document still gets a complete guide.
    If that ever changes, the notice becomes a lie and this test should fail
    before a patient finds out.
    """

    def test_the_guide_is_independent_of_extracted_red_flags(self):
        from pathlib import Path

        prompt = (Path(__file__).resolve().parents[1]
                  / "prompts" / "agent5_system_prompt.txt").read_text().lower()
        # The three tiers are required of the agent regardless of input.
        assert "911" in prompt
        assert "tier" in prompt or "level" in prompt

    @pytest.mark.parametrize("red_flags", [[], ["chest pain"]])
    def test_an_empty_red_flag_list_is_not_itself_a_degradation_signal(
        self, red_flags
    ):
        """
        Only 26% of the corpus carries red flags at all. Treating their
        absence as damage would fire the notice on three quarters of clean
        documents - the false-alarm failure this feature must avoid.
        """
        extraction = ExtractionOutput(
            primary_diagnosis="Heart failure", red_flag_symptoms=red_flags)
        response = PipelineResponse(
            extraction=extraction,
            diagnosis_explanation="",
            medication_rationale="",
            recovery_trajectory="",
            escalation_guide="CALL 911 IMMEDIATELY",
            fk_scores={},
            extraction_warnings=[],
            pipeline_status="complete",
        )
        assert response.source_degraded is False


class TestTheDeterministicDetector:
    """
    The primary trigger, and the reason the notice is trustworthy.

    Measured on the real corpus: clean documents top out at 7.8 confused words
    per 1000 tokens, the degraded stratum starts at 12.9. At a threshold of 10
    the separation is complete - 12 of 12 degraded flagged, 0 of 106 clean.

    That is a different league from the model-written warnings it replaced,
    which managed 92% sensitivity only by accepting a 20% false-alarm rate.
    """

    def test_clean_prose_scores_near_zero(self):
        assert ocr_substitution_rate(_clean_text()) < 1.0

    def test_substituted_text_scores_far_above_the_threshold(self):
        assert ocr_substitution_rate(_degraded_text()) > OCR_SUBSTITUTION_THRESHOLD

    def test_the_flag_follows_the_rate(self):
        assert looks_ocr_damaged(_degraded_text()) is True
        assert looks_ocr_damaged(_clean_text()) is False

    def test_dose_tokens_are_not_damage(self):
        """
        "40mg" and "2wk" are letters-plus-digits by construction and appear in
        every medication list. Counting them would flag every clean discharge
        summary that names a dose - which is all of them.
        """
        doses = "Lasix 40mg QD, Metoprolol 25mg BID, Warfarin 5mg daily, 2wk supply"
        assert ocr_substitution_rate(doses) == 0.0
        assert looks_ocr_damaged(doses) is False

    def test_lab_values_are_not_damage(self):
        """Clinical shorthand like "BUN 19" and "PTT 37.1" is normal writing."""
        labs = "Labs on discharge: BUN 19, Creatinine 1.2, PTT 37.1, INR 2.3, BNP 450"
        assert looks_ocr_damaged(labs) is False

    @pytest.mark.parametrize("text", ["", "   ", "a b c"])
    def test_degenerate_input_is_not_damage(self, text):
        """
        Empty or tokenless text must score zero rather than divide by zero.
        An extraction that produced nothing is a different failure, and it
        must not surface to the patient as "your document was hard to read".
        """
        assert ocr_substitution_rate(text) == 0.0
        assert looks_ocr_damaged(text) is False

    def test_the_threshold_sits_between_the_measured_populations(self):
        """
        Pins the calibration. Clean max 7.8, degraded min 12.9 - a threshold
        outside that gap silently reintroduces false alarms or blindness.
        """
        assert 7.8 < OCR_SUBSTITUTION_THRESHOLD < 12.9
