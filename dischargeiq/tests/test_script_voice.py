"""
Audio scripts speak to this patient, not about people in general.

Frank Naeymi-Rad, 10 Sep 2026: emphasise patient-specific instructions over
collective language, for accuracy and liability.

The live example, from `dischargeiq/media/surgical.script.txt`:

    Sam: Most people feel better in one to two weeks.

Two sentences are hiding in that. "Your plan says you should feel better in
one to two weeks" reports what a clinician wrote for this person. "Most people
feel better in one to two weeks" is a claim about a population, delivered in a
calm voice to someone who has just had surgery - and if their recovery is
slower, the app has told them they are behind. The fact may be identical; the
speaker is not.

The hard part is not detection, it is NOT over-detecting. A check that fires on
correct output gets switched off, and then it protects nothing. So roughly half
of these tests assert silence.
"""

import pytest

from dischargeiq.utils.script_voice import collective_claims, describe


class TestTheRealCase:
    def test_the_sentence_that_prompted_this(self):
        claims = collective_claims(
            "Sam: Most people feel better in one to two weeks.")
        assert len(claims) == 1
        assert claims[0].phrase.lower() == "most people"
        assert claims[0].speaker == "Sam"

    def test_the_shipped_surgical_script_is_caught(self):
        script = (
            "Sam: Your surgery went well.\n"
            "Alex: Start walking a little each day at home.\n"
            "Sam: Most people feel better in one to two weeks.\n"
            "Alex: Full healing may take two to four weeks.\n"
        )
        claims = collective_claims(script)
        assert len(claims) == 1
        assert "Most people" in claims[0].sentence


class TestWhatMustBeFlagged:
    @pytest.mark.parametrize("sentence", [
        "Most people feel better within days.",
        "Many people notice swelling afterwards.",
        "People usually get their strength back slowly.",
        "Patients often feel tired for a while.",
        "It is common to feel sore.",
        "It's normal to have a small appetite.",
        "Everyone heals at their own pace.",
        "Most patients go back to work soon.",
        "Typically, the swelling settles down.",
    ])
    def test_a_population_claim_is_flagged(self, sentence):
        assert collective_claims(f"Sam: {sentence}"), sentence

    def test_each_offending_sentence_is_reported_separately(self):
        """
        A reviewer needs to know which sentence to rewrite, not which speaker
        line contained something wrong.
        """
        claims = collective_claims(
            "Sam: Your plan is simple. Most people feel better soon. "
            "It is common to be tired.")
        assert len(claims) == 2

    def test_the_report_names_the_sentence(self):
        text = describe(collective_claims("Alex: Most people rest for a while."))
        assert "Most people" in text and "Alex" in text


class TestWhatMustStaySilent:
    """
    The over-detection side. Every one of these is correct output, and a check
    that flags them is a check somebody disables.
    """

    @pytest.mark.parametrize("sentence", [
        "Your plan says you should feel better in one to two weeks.",
        "Your care team wrote that walking will help.",
        "Take your water pill each morning.",
        "Your summary lists most of your medicines as unchanged.",
        "Your doctor will usually call you first.",
        "Call your doctor if you gain weight quickly.",
        "You may feel tired for a few days.",
        "Your document does not say when to stop.",
    ])
    def test_patient_voice_is_never_flagged(self, sentence):
        assert not collective_claims(f"Sam: {sentence}"), sentence

    def test_a_collective_word_anchored_to_the_patient_is_allowed(self):
        """
        "Your plan says most of your medicines continue" is about this
        patient's medicines. The target is the SUBJECT of the claim, not the
        vocabulary - a word-list check without this would fail correct text.
        """
        assert not collective_claims(
            "Sam: Your plan says most of your medicines continue.")

    def test_an_empty_or_blank_script_is_quiet(self):
        assert collective_claims("") == []
        assert collective_claims("   \n  \n") == []

    def test_prose_without_speakers_still_works(self):
        claims = collective_claims("Most people feel better in a week.")
        assert len(claims) == 1
        assert claims[0].speaker == ""


class TestTheHeartFailureScriptIsClean:
    def test_a_correct_script_produces_nothing(self):
        script = (
            "Sam: Your heart was not pumping as well as it should.\n"
            "Alex: Your plan says to weigh yourself each morning.\n"
            "Sam: Call your doctor if you gain weight quickly.\n"
            "Alex: Take your water pill exactly as written.\n"
        )
        assert collective_claims(script) == []
