#!/usr/bin/env python3
"""
scripts/escalation_template_status.py

Shows which escalation templates a physician has signed, and therefore which
parts of the highest-risk output are still generated without clinician
authority. Owner: Likitha Shankar.

Item 2.2 of the Dr. Liebovitz faculty review asks for tiers anchored to
clinician-authored criteria with physician sign-off. The templates exist; the
signatures are the remaining work, and that work happens outside this
repository. This script is how you tell what is left, and what to put in front
of a reviewer.

Makes no API calls and reads only local files.

Usage:
    python scripts/escalation_template_status.py
"""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from dischargeiq.utils.escalation_templates import (  # noqa: E402 - path above
    TIER_911,
    TIER_DOCTOR,
    TIER_ER,
    load_all,
)


def main() -> None:
    """Print per-template signature state and a plain summary of what it means."""
    templates = load_all()
    if not templates:
        print("No escalation templates found in templates/escalation/.")
        return

    print(f"{'template':18} {'911':>4} {'ER':>4} {'DOC':>4}  {'signed by':28} date")
    print("-" * 78)
    for template in templates:
        print(
            f"{template.diagnosis_key:18} "
            f"{len(template.tiers[TIER_911]):>4} "
            f"{len(template.tiers[TIER_ER]):>4} "
            f"{len(template.tiers[TIER_DOCTOR]):>4}  "
            f"{(template.reviewed_by or '-- UNSIGNED --'):28} "
            f"{template.reviewed_date or '-'}"
        )

    signed = [t for t in templates if t.is_signed]
    print()
    print(f"signed: {len(signed)} of {len(templates)}")

    if not signed:
        # Say what this actually means for patients rather than leaving a
        # reader to infer that having template files is itself progress.
        print()
        print("No template is signed, so NONE of them govern output today.")
        print("Agent 5 still generates all three tiers, exactly as before.")
        print("The templates are drafts FOR review; they are inert until signed.")
        print()
        print("To advance item 2.2: send templates/escalation/*.md to the")
        print("reviewer, have them correct the criteria and fill in the")
        print("'Reviewed by' and 'Date' fields, then re-run this script.")
    else:
        print()
        print("Signed templates are authoritative: verify_guide() will report a")
        print("Tier 1 criterion that a generated guide demoted or dropped.")
        unsigned = [t.diagnosis_key for t in templates if not t.is_signed]
        if unsigned:
            print(f"Still unsigned and therefore inert: {', '.join(unsigned)}")


if __name__ == "__main__":
    main()
