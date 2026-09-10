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

from dischargeiq.utils.script_voice import (
    collective_claims,
    describe,
    strip_collective_adverbs,
)


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


class TestBareAdverbs:
    """
    Found by READING the regenerated surgical script, an hour after this check
    shipped clean on it. "Full healing usually takes two to four weeks" is a
    claim about a population with no subject at all, and the pattern required
    the word "people" next to the adverb.

    A detector that only catches the phrasing you already thought of is a
    detector that reports zero and means nothing.
    """

    @pytest.mark.parametrize("sentence", [
        "Full healing usually takes two to four weeks.",
        "Recovery typically takes a few weeks.",
        "The swelling normally settles down.",
        "Healing generally goes well.",
    ])
    def test_a_bare_adverb_claim_is_flagged(self, sentence):
        assert collective_claims(f"Sam: {sentence}"), sentence

    @pytest.mark.parametrize("sentence", [
        "Your doctor will usually call you first.",
        "Your care team normally checks in after a week.",
        "Your plan says healing usually takes a while.",
    ])
    def test_the_patient_voice_exemption_carries_the_weight(self, sentence):
        """
        Broadening to bare adverbs only works because these stay silent. The
        exemption is load-bearing, not a convenience - without it the check
        fires on correct output and gets switched off.
        """
        assert not collective_claims(f"Sam: {sentence}"), sentence


class TestStrippingAddedAdverbs:
    """
    Two prompt revisions failed to stop the model writing "Full healing USUALLY
    takes two to four weeks" from a source that says only "Full healing takes
    two to four weeks". That matches the four revisions that failed on invented
    thresholds, and the answer is the same: fix it after generation.

    The justification for doing this automatically is narrow and load-bearing.
    It DELETES A WORD the model added; it does not rewrite a claim or decide
    anything clinical. Restoring the source's own wording is safe. Rewriting
    the numeric timeline in that same sentence would not be, and is left alone.
    """

    def test_the_adverb_goes_and_the_sentence_survives(self):
        out, changed = strip_collective_adverbs(
            "Sam: Full healing usually takes two to four weeks.")
        assert out == "Sam: Full healing takes two to four weeks."
        assert len(changed) == 1

    def test_the_clinical_content_is_untouched(self):
        """Only the adverb. The timeline is a clinician's call, not a regex's."""
        out, _ = strip_collective_adverbs(
            "Sam: Full healing usually takes two to four weeks.")
        assert "two to four weeks" in out

    @pytest.mark.parametrize("adverb", ["usually", "typically", "generally", "normally"])
    def test_all_four_adverbs_are_stripped(self, adverb):
        out, changed = strip_collective_adverbs(f"Sam: Healing {adverb} goes well.")
        assert adverb not in out.lower()
        assert changed

    def test_patient_voice_keeps_its_adverb(self):
        """
        "Your doctor will usually call you first" is correct, and the adverb is
        doing real work. Stripping it would change what the sentence means.
        """
        text = "Alex: Your doctor will usually call you first."
        out, changed = strip_collective_adverbs(text)
        assert out == text
        assert changed == []

    def test_it_cannot_launder_a_real_collective_claim(self):
        """
        The important limit. Stripping must not turn something this check
        would refuse into something it accepts - "most people" is a claim
        about a population and no word deletion makes it patient-specific.
        """
        out, _ = strip_collective_adverbs("Sam: Most people feel better soon.")
        assert collective_claims(out), "a refusable claim was laundered into a pass"

    def test_speaker_labels_and_blank_lines_survive(self):
        script = "Sam: Healing usually goes well.\n\nAlex: Rest when you can."
        out, _ = strip_collective_adverbs(script)
        assert out.splitlines()[0].startswith("Sam:")
        assert "Alex: Rest when you can." in out

    def test_a_clean_script_is_returned_unchanged(self):
        script = "Sam: Take your water pill each morning."
        out, changed = strip_collective_adverbs(script)
        assert out == script and changed == []

    def test_empty_input_is_safe(self):
        assert strip_collective_adverbs("") == ("", [])
