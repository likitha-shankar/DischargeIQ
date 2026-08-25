"""
Tests for physician-signed escalation templates
(dischargeiq/utils/escalation_templates.py).

Answers item 2.2 of the Dr. Liebovitz faculty review: the three-tier escalation
guide is the highest-risk output because it delivers triage advice with no
clinician in the loop, so tiers should be anchored to clinician-authored
criteria with physician sign-off.

The load-bearing test here is `test_unsigned_template_enforces_nothing`. A
template drafted in-repo and treated as authoritative would be worse than
generated text: the same clinical risk, now labelled clinician-reviewed. The
signature is the whole guarantee, so it is tested harder than the parsing.
"""

import pytest

from dischargeiq.utils.escalation_templates import (
    TIER_911,
    TIER_DOCTOR,
    TIER_ER,
    load_all,
    load_template,
    verify_guide,
)

_UNSIGNED = """# Test - Escalation Tier Template

## CALL 911 IMMEDIATELY
- Cannot breathe or gasping
- Seizure

## GO TO THE ER TODAY
- Fever above 101 degrees

## CALL YOUR DOCTOR
- Mild pain getting better

## Clinical sign-off

**Reviewed by:** [Pending - Dr. Liebovitz / designated reviewer]
**Date:** [Pending]
"""

_SIGNED = _UNSIGNED.replace(
    "**Reviewed by:** [Pending - Dr. Liebovitz / designated reviewer]",
    "**Reviewed by:** Dr. David Liebovitz",
).replace("**Date:** [Pending]", "**Date:** 2026-09-01")


@pytest.fixture
def template_dir(tmp_path):
    """A throwaway template directory, so tests never depend on real files."""
    return tmp_path


def _write(directory, name, body):
    """Write one template file and return its diagnosis key."""
    (directory / f"{name}.md").write_text(body, encoding="utf-8")
    return name


class TestSignatureGating:
    """The signature is the guarantee, so it is tested hardest."""

    def test_placeholder_signoff_is_not_signed(self, template_dir):
        """
        '[Pending - ...]' must never read as a signature.

        This is the exact placeholder used by the existing diagnosis templates,
        so getting it wrong would mark every draft in the repo as reviewed.
        """
        _write(template_dir, "test", _UNSIGNED)
        template = load_template("test", template_dir)
        assert template.reviewed_by == ""
        assert template.is_signed is False
        assert template.is_authoritative is False

    def test_real_signoff_is_authoritative(self, template_dir):
        _write(template_dir, "test", _SIGNED)
        template = load_template("test", template_dir)
        assert template.reviewed_by == "Dr. David Liebovitz"
        assert template.reviewed_date == "2026-09-01"
        assert template.is_authoritative is True

    def test_name_without_date_is_not_signed(self, template_dir):
        """A name with no date could predate any number of edits."""
        body = _SIGNED.replace("**Date:** 2026-09-01", "**Date:** [Pending]")
        _write(template_dir, "test", body)
        assert load_template("test", template_dir).is_signed is False

    def test_date_without_name_is_not_signed(self, template_dir):
        """A date with no name is not attributable to anyone."""
        body = _SIGNED.replace("**Reviewed by:** Dr. David Liebovitz",
                               "**Reviewed by:** [Pending]")
        _write(template_dir, "test", body)
        assert load_template("test", template_dir).is_signed is False

    def test_unsigned_template_enforces_nothing(self, template_dir):
        """
        The core safety property of this whole feature.

        An unsigned template must not shape patient-facing output, even when
        the guide plainly contradicts it. Otherwise adding a file to the repo
        silently changes triage advice with no clinician behind it.
        """
        _write(template_dir, "test", _UNSIGNED)
        template = load_template("test", template_dir)
        guide = f"{TIER_911}\nNothing here.\n{TIER_ER}\nNothing.\n{TIER_DOCTOR}\nNothing."
        assert verify_guide(guide, template) == []


class TestParsing:
    """Tier extraction has to be exact, since the UI parses the same headers."""

    def test_tiers_are_parsed(self, template_dir):
        _write(template_dir, "test", _UNSIGNED)
        tiers = load_template("test", template_dir).tiers
        assert tiers[TIER_911] == ["Cannot breathe or gasping", "Seizure"]
        assert tiers[TIER_ER] == ["Fever above 101 degrees"]
        assert tiers[TIER_DOCTOR] == ["Mild pain getting better"]

    def test_signoff_bullets_do_not_leak_into_tiers(self, template_dir):
        """A later section must end the preceding tier block."""
        _write(template_dir, "test", _UNSIGNED)
        tiers = load_template("test", template_dir).tiers
        assert all("Reviewed" not in c for tier in tiers.values() for c in tier)

    def test_missing_template_is_not_an_error(self, template_dir):
        """No template means Agent 5 keeps its current behaviour."""
        assert load_template("nonexistent", template_dir) is None

    def test_format_docs_are_skipped(self, template_dir):
        """Underscore-prefixed files are documentation, not templates."""
        _write(template_dir, "_FORMAT", _UNSIGNED)
        _write(template_dir, "real", _UNSIGNED)
        assert [t.diagnosis_key for t in load_all(template_dir)] == ["real"]


class TestGuideVerification:
    """Only Tier 1 demotion is enforced, and only for signed templates."""

    def test_guide_covering_tier1_passes(self, template_dir):
        _write(template_dir, "test", _SIGNED)
        template = load_template("test", template_dir)
        guide = (
            f"{TIER_911}\n- Cannot breathe or gasping: call now.\n- Seizure: call now.\n"
            f"{TIER_ER}\n- Fever above 101 degrees: go in.\n"
            f"{TIER_DOCTOR}\n- Mild pain getting better: call the office."
        )
        assert verify_guide(guide, template) == []

    def test_demoted_tier1_criterion_is_caught(self, template_dir):
        """A 911 criterion appearing only in a lower tier is the real danger."""
        _write(template_dir, "test", _SIGNED)
        template = load_template("test", template_dir)
        guide = (
            f"{TIER_911}\n- Cannot breathe or gasping: call now.\n"
            f"{TIER_ER}\n- Seizure: go to the ER today.\n"
            f"{TIER_DOCTOR}\n- Mild pain getting better: call the office."
        )
        problems = verify_guide(guide, template)
        assert len(problems) == 1
        assert "Seizure" in problems[0]

    def test_rephrasing_is_not_a_violation(self, template_dir):
        """Plain-language rewording is the product working, not failing."""
        _write(template_dir, "test", _SIGNED)
        template = load_template("test", template_dir)
        guide = (
            f"{TIER_911}\n- Cannot breathe, gasping for air: minutes matter.\n"
            f"- Seizure or shaking fit: call now.\n"
            f"{TIER_ER}\n- Fever: go in.\n{TIER_DOCTOR}\n- Mild pain: call."
        )
        assert verify_guide(guide, template) == []

    def test_missing_tier1_header_is_reported(self, template_dir):
        _write(template_dir, "test", _SIGNED)
        template = load_template("test", template_dir)
        problems = verify_guide(f"{TIER_ER}\n- Fever: go in.", template)
        assert problems and "missing" in problems[0]


class TestShippedTemplates:
    """Guards on the real files in templates/escalation/."""

    def test_no_shipped_template_is_signed_yet(self):
        """
        Fails the day someone signs one, which is the point.

        When Dr. Liebovitz signs a template, this test must be updated
        deliberately - forcing a human to notice that triage advice has started
        being governed by a template, rather than it happening quietly.
        """
        signed = [t.diagnosis_key for t in load_all() if t.is_signed]
        assert signed == [], (
            f"templates now signed: {signed}. This is expected once review "
            "happens - update this test and confirm verify_guide is wired in."
        )

    def test_shipped_templates_parse_with_tier1_criteria(self):
        """A template with no Tier 1 content would enforce nothing once signed."""
        for template in load_all():
            assert template.tiers[TIER_911], f"{template.diagnosis_key} has no Tier 1"
