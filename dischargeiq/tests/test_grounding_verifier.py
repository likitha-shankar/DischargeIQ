"""
Tests for the post-hoc grounding verifier (dischargeiq/utils/grounding.py).

The verifier answers item 3.2 of the Dr. Liebovitz faculty review: no
fabrication is currently a prompt constraint rather than an architectural
guarantee, so every clinical entity and number in an output should be matched
against the extraction record.

The most important test here is `test_unchecked_is_not_clean`. A verifier that
reports "clean" when it had nothing to check against is worse than no verifier,
because it converts a missing check into a passing grade. Everything else in
this file is about keeping the signal honest enough to eventually promote from
report-only to enforcement.
"""

from pathlib import Path

from dischargeiq.utils import grounding
from dischargeiq.utils.grounding import verify_output

_SOURCE = (
    "Discharge summary. Patient started on furosemide 40 mg daily and "
    "metoprolol 25 mg twice daily. Call the office for fever over 100.5. "
    "Follow up in 2 weeks."
)


def _output(**kwargs):
    """Build a PipelineResponse-shaped dict with only the fields under test."""
    base = {
        "extraction": {"medications": []},
        "diagnosis_explanation": "",
        "medication_rationale": "",
        "recovery_trajectory": "",
        "escalation_guide": "",
    }
    base.update(kwargs)
    return base


class TestSourceAvailability:
    """An unchecked output must never read as a passing one."""

    def test_unchecked_is_not_clean(self):
        """
        No source text means no verdict.

        This is the failure mode that would make the whole verifier
        counterproductive: a run where the corpus was not on disk would report
        zero findings across every document and look like a perfect score.
        """
        report = verify_output(_output(), source_text="")
        assert report.source_available is False
        assert report.is_clean is False
        assert report.findings == []

    def test_checked_and_empty_is_clean(self):
        """A genuine pass still has to be expressible."""
        report = verify_output(_output(), source_text=_SOURCE)
        assert report.source_available is True
        assert report.is_clean is True


class TestMedicationGrounding:
    """Agent 1's contract forbids inventing a drug name, so there is no benign class."""

    def test_grounded_medication_passes(self):
        out = _output(extraction={"medications": [{"name": "Furosemide 40mg"}]})
        assert verify_output(out, _SOURCE).is_clean

    def test_invented_medication_is_caught(self):
        out = _output(extraction={"medications": [{"name": "Lisinopril 10mg"}]})
        report = verify_output(out, _SOURCE)
        assert not report.is_clean
        assert [f.value for f in report.findings] == ["Lisinopril 10mg"]
        assert report.findings[0].category == "invented"

    def test_short_names_are_not_evidence(self):
        """A two-letter token matches too much text to mean anything."""
        out = _output(extraction={"medications": [{"name": "K"}]})
        assert verify_output(out, _SOURCE).is_clean


class TestNumberGrounding:
    """Dosages, weights and thresholds are the numbers that matter."""

    def test_number_present_in_source_passes(self):
        out = _output(escalation_guide="Call for fever over 100.5.")
        assert verify_output(out, _SOURCE).is_clean

    def test_ordinary_counts_are_not_clinical_claims(self):
        """Week numbers and 911 must not generate noise."""
        out = _output(
            recovery_trajectory="In week 1 rest. In week 2 walk.",
            escalation_guide="Call 911 if you cannot breathe.",
        )
        assert verify_output(out, _SOURCE).is_clean

    def test_invented_number_is_caught(self):
        """The Agent 4 activity-target case from the 16 Aug corpus run."""
        out = _output(recovery_trajectory="Walk for 35 minutes each day.")
        report = verify_output(out, _SOURCE)
        assert [f.value for f in report.findings] == ["35"]
        assert report.findings[0].category == "invented"
        assert report.findings[0].agent == "agent4"

    def test_no_threshold_is_excused_any_more(self):
        """
        Nothing is excused, because no prompt supplies a threshold now.

        101 used to be filed as "prompt_threshold" and kept out of
        invented_findings, which was honest - agent5_system_prompt.txt really
        did supply it - and it hid the measurement. A 25 Aug corpus re-run
        showed Agent 5 emitting "Fever above 101 degrees" for documents that
        mention no fever at all, and the report called those outputs clean.
        The prompts no longer hand the model any threshold, so an ungrounded
        101 is now what it always was: invented.
        """
        out = _output(escalation_guide="Call for a fever over 101 degrees.")
        report = verify_output(out, _SOURCE)
        assert [f.category for f in report.findings] == ["invented"]
        assert len(report.invented_findings) == 1
        assert report.is_clean is False

    def test_classification_still_works_if_a_prompt_supplies_one(self, monkeypatch):
        """
        The prompt_threshold category is kept, not deleted.

        If a clinician-signed template later authorises a specific default,
        a prompt may legitimately supply it again, and that is a different
        finding from a number the model invented: one is an attribution
        question, the other is a bug. This proves the mechanism survives an
        empty list so re-populating it does not need new code.
        """
        monkeypatch.setattr(grounding, "_PROMPT_SUPPLIED_THRESHOLDS",
                            frozenset({"101"}))
        out = _output(escalation_guide="Call for a fever over 101 degrees.")
        report = verify_output(out, _SOURCE)
        assert [f.category for f in report.findings] == ["prompt_threshold"]
        assert report.invented_findings == []

    def test_only_real_prompt_numbers_are_excused(self):
        """
        The excuse list must match what the prompts actually say.

        It once held 100.4, 101.5 and 102, none of which appear in any prompt
        file. Ten genuinely invented thresholds were therefore being filed as
        "the prompt supplied it" and kept out of invented_findings. A
        classifier that quietly downgrades real findings is worse than none,
        because the count looks clean for the wrong reason.
        """
        out = _output(escalation_guide="Call for a fever over 100.4 degrees.")
        report = verify_output(out, _SOURCE)
        assert [f.category for f in report.findings] == ["invented"]
        assert len(report.invented_findings) == 1

    def test_excuse_list_never_exceeds_what_prompts_supply(self):
        """
        Every excused number must actually appear in a prompt file.

        Checked against the prompt files themselves rather than against the
        constant, because the two drifting apart is precisely the failure that
        happened: the list held 100.4, 101.5 and 102 while no prompt contained
        them, and ten real findings were filed as "the prompt said so".

        Empty is the correct state today and this test passes trivially. It
        earns its place the day someone re-populates the list.
        """
        prompts = Path(__file__).resolve().parents[1] / "prompts"
        corpus = " ".join(
            path.read_text(encoding="utf-8") for path in prompts.glob("*.txt")
        )
        for value in grounding._PROMPT_SUPPLIED_THRESHOLDS:
            assert value in corpus, (
                f"{value!r} is excused as prompt-supplied but appears in no "
                "prompt file, so it is hiding a real finding"
            )

    def test_repeated_number_reported_once(self):
        """One ungrounded value is one finding, however often it is repeated."""
        out = _output(recovery_trajectory="Walk 35 minutes. Then 35 minutes more.")
        report = verify_output(out, _SOURCE)
        assert len(report.findings) == 1

    def test_finding_records_which_agent_to_fix(self):
        """A finding nobody can route is a finding nobody acts on."""
        out = _output(medication_rationale="Take 999 mg each morning.")
        finding = verify_output(out, _SOURCE).findings[0]
        assert finding.agent == "agent3"
        assert finding.field == "medication_rationale"
        assert finding.kind == "number"
