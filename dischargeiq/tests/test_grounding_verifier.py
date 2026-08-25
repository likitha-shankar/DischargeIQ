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

    def test_prompt_threshold_is_classified_separately(self):
        """
        A prompt-supplied fever threshold is not the same defect as an
        invented activity target, and must not be reported as one.

        It is still a finding: showing standard guidance as though the
        patient's own paperwork said so is the attribution problem the review
        flags for clinician decision. But the fix is a clinical call about
        attribution, not a code bug, so it is kept out of invented_findings.
        """
        out = _output(escalation_guide="Call for a fever over 101 degrees.")
        report = verify_output(out, _SOURCE)
        assert [f.category for f in report.findings] == ["prompt_threshold"]
        assert report.invented_findings == []
        assert report.is_clean is False

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
