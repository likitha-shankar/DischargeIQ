"""
Tests for Agent 5's degenerate-explanation detector and its retry guard.

Background. On 25 Aug 2026 Agent 5 produced a guide for a global-aphasia
(stroke) patient in which six bullets all carried the same explanation, "This
is a medical emergency." The guide looked full and told the patient nothing
about why any individual symptom mattered, which is the entire job of the half
after the colon. It scored FK 7.83 against a 6.0 target.

Two things were wrong, and only one was the model's fault. The prompt already
forbids explanations opening with "This is", so the instruction existed and was
ignored. But Agent 5 had no retry: it logged "FK FAIL - revise
agent5_system_prompt.txt" and shipped the guide anyway. Agent 2 has had a
retry for its own failure mode since July.

The detector is deliberately blunt and the retry guard is deliberately
suspicious, because this is a safety-critical output and the cheapest way for
a model to satisfy "vary the explanations" is to emit fewer symptoms.
"""

import pytest

from dischargeiq.agents.escalation_agent import _degenerate_explanations

_HEALTHY = """CALL 911 IMMEDIATELY
These symptoms are life-threatening. Do not drive yourself.
- Cannot breathe or gasping: Your body is not getting oxygen.
- Face drooping or arm weakness: These are stroke signs. Minutes matter.
- Chest pain that will not stop: Your heart may be starving of blood.

GO TO THE ER TODAY
Do not wait until tomorrow. Go within a few hours.
- Fever that will not come down: You may have an infection.
- Wound draining pus: The cut is infected.

CALL YOUR DOCTOR
Call during office hours. Do not go to the ER for these.
- Mild swelling without pain: This can happen while you heal.
"""


class TestDetectsDegeneracy:
    """The two shapes seen in real output."""

    def test_the_mtsamples_005_case(self):
        """Six identical explanations, verbatim from the 25 Aug run."""
        guide = "CALL 911 IMMEDIATELY\n" + "\n".join(
            f"- Symptom {i}: This is a medical emergency." for i in range(6)
        )
        reason = _degenerate_explanations(guide)
        assert reason is not None
        assert "repeated 6 times" in reason

    def test_three_repeats_is_enough(self):
        """
        Three identical explanations is not coincidence.

        It is a model that has stopped reading the symptom it is explaining,
        and the threshold is set low on purpose: the cost of one extra
        regeneration is far below the cost of shipping a guide that explains
        nothing.
        """
        guide = "CALL 911 IMMEDIATELY\n" + "\n".join(
            f"- Symptom {i}: Call right now." for i in range(3)
        )
        assert _degenerate_explanations(guide) is not None

    def test_empty_openers_are_caught(self):
        """Explanations that spend words without naming a cause or risk."""
        guide = (
            "CALL 911 IMMEDIATELY\n"
            "- Chest pain: This is serious.\n"
            "- Sudden confusion: This means trouble.\n"
            "- Severe bleeding: You may feel faint.\n"
        )
        reason = _degenerate_explanations(guide)
        assert reason is not None
        assert "empty phrase" in reason


class TestDoesNotFireOnGoodOutput:
    """
    False positives cost a real API call and a real delay every time.

    Worse, a detector that fires on healthy output trains everyone to ignore
    the warning, which is how the FK FAIL log was already being treated.
    """

    def test_healthy_guide_passes(self):
        assert _degenerate_explanations(_HEALTHY) is None

    def test_two_repeats_is_tolerated(self):
        """
        Two matching explanations can happen honestly.

        "You may have an infection" legitimately fits both a fever and a
        draining wound. Flagging that would punish correct output.
        """
        guide = (
            "GO TO THE ER TODAY\n"
            "- Fever that will not come down: You may have an infection.\n"
            "- Wound draining pus: You may have an infection.\n"
            "- Severe pain: Medicine is not controlling it.\n"
        )
        assert _degenerate_explanations(guide) is None

    def test_one_empty_opener_is_tolerated(self):
        """One slip is not a pattern, and the tier subtitles use this phrasing."""
        guide = (
            "CALL YOUR DOCTOR\n"
            "- Mild swelling without pain: This can happen while you heal.\n"
            "- Questions about a medicine: Your doctor can explain the dose.\n"
        )
        assert _degenerate_explanations(guide) is None

    @pytest.mark.parametrize("guide", ["", "CALL 911 IMMEDIATELY", "no bullets here"])
    def test_no_bullets_never_raises(self, guide):
        """
        This runs on every escalation output, including failed ones.

        An empty or malformed guide is a pipeline problem handled elsewhere;
        it must not be turned into an exception here.
        """
        assert _degenerate_explanations(guide) is None

    def test_bullet_without_colon_is_ignored(self):
        """Not every bullet carries an explanation; those are not evidence."""
        guide = "CALL 911 IMMEDIATELY\n- Chest pain\n- Sudden confusion\n- Fainting\n"
        assert _degenerate_explanations(guide) is None
