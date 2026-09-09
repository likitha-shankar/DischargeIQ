"""
Grounding check on the generated TTS dialogue script.

The script is the last place a fabrication reaches a patient unguarded. Agent
output is checked by the threshold guard and by the extraction contract; the
audio script was checked by nothing until now, and prompt rules of the shape
"never add a symptom the plan does not contain" have failed twice elsewhere in
this codebase.

The example that prompted this module was NOT a real fabrication, and saying
so matters. A script naming "leg muscle spasms" looked invented; the phrase is
in the escalation guide and in the source document. The search was for "leg
spasm", which does not substring-match, and a failed match was read as an
invention. The checker is keyed on bare tokens because of that near-miss, and
`test_a_multi_word_variant_is_still_caught` pins it.

Two properties, and the second is the one that keeps this usable:

  An invented symptom is caught. That is the defect.

  A legitimate plain-language translation is NOT caught. "Hemoptysis" in the
  extraction licenses "cough up blood" in the script - that translation IS
  the product. A checker that rejected it would refuse audio for doing its
  job, and a false rejection silently removes a patient's audio.
"""

import pytest

from dischargeiq.utils.script_grounding import verify_script_grounding


def _payload(**over) -> dict:
    base = {
        "extraction": {
            "primary_diagnosis": "Status post right total hip replacement",
            "red_flag_symptoms": [
                "chest pain",
                "difficulty breathing",
                "hemoptysis",
            ],
            "medications": [{"name": "Coumadin"}],
        },
        "escalation_guide": (
            "CALL 911 IMMEDIATELY\n"
            "- Chest pain that will not stop\n"
            "GO TO THE ER TODAY\n"
            "- Calf pain or swelling: This could be a blood clot."
        ),
        "recovery_trajectory": "Week 1: rest and keep the incision dry.",
    }
    base.update(over)
    return base


class TestInventedSymptomsAreCaught:
    """The defect that prompted this."""

    def test_a_symptom_absent_from_the_payload_is_caught(self):
        """
        The payload here names no spasm anywhere, so a script that mentions
        one is claiming something the care plan does not support.
        """
        script = ("Sam: Call your doctor if you have calf pain or leg spasms.\n"
                  "Alex: We are here to help you heal.")
        report = verify_script_grounding(script, _payload())
        assert not report.is_grounded
        assert "spasm" in report.ungrounded_symptoms

    def test_a_multi_word_variant_is_still_caught(self):
        """
        The check is keyed on the bare token for this reason. An earlier
        version keyed on "leg spasm" and missed "leg MUSCLE spasms" - the same
        claim two words apart. That near-miss also produced a false
        fabrication report against a script that was in fact grounded.
        """
        script = "Sam: Watch for leg muscle spasms."
        assert not verify_script_grounding(script, _payload()).is_grounded

    @pytest.mark.parametrize("symptom", [
        "seizure", "vomiting blood", "black stool", "blurred vision",
    ])
    def test_other_invented_symptoms_are_caught(self, symptom):
        script = f"Sam: Call 911 if you have {symptom}."
        report = verify_script_grounding(script, _payload())
        assert symptom in report.ungrounded_symptoms


class TestLegitimateContentIsNotRejected:
    """
    The half that decides whether this can ship. A false rejection removes a
    patient's audio for no reason.
    """

    def test_plain_language_translation_of_a_clinical_term_is_grounded(self):
        """
        "Hemoptysis" -> "cough up blood" is the translation this product
        exists to perform. Rejecting it would punish the system for working.
        """
        script = "Sam: Call 911 if you cough up blood."
        assert verify_script_grounding(script, _payload()).is_grounded

    def test_a_symptom_from_agent_5s_universal_tiers_is_grounded(self):
        """
        "Calf pain" is not in this patient's document - it comes from Agent
        5's universal criteria, which are legitimate content the script may
        repeat. Grounding is checked against the whole payload, not just the
        extraction, for exactly this reason.
        """
        script = "Sam: Go to the ER for calf pain."
        assert verify_script_grounding(script, _payload()).is_grounded

    def test_an_extracted_red_flag_is_grounded(self):
        script = "Sam: Call 911 for chest pain."
        assert verify_script_grounding(script, _payload()).is_grounded

    def test_a_script_naming_nothing_checked_is_grounded(self):
        script = ("Sam: You had a hip replacement. Rest this week.\n"
                  "Alex: Keep taking your medicines as prescribed.")
        assert verify_script_grounding(script, _payload()).is_grounded


class TestFailureModes:
    """A checker that breaks must fail toward keeping the audio."""

    def test_an_empty_payload_disables_the_check(self):
        """
        With nothing to compare against every phrase reads as ungrounded, so
        a missing payload would refuse every script - turning an input error
        into a total audio outage.
        """
        script = "Sam: Call 911 if you have a seizure."
        assert verify_script_grounding(script, {}).is_grounded

    @pytest.mark.parametrize("script", ["", None])
    def test_an_empty_script_is_not_a_grounding_failure(self, script):
        assert verify_script_grounding(script, _payload()).is_grounded

    def test_matching_is_case_insensitive(self):
        script = "Sam: Call 911 if you have a SEIZURE."
        assert not verify_script_grounding(script, _payload()).is_grounded
