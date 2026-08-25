"""
File: dischargeiq/utils/escalation_templates.py
Owner: Likitha Shankar
Description: Loads physician-signed escalation-tier templates and verifies a
  generated guide against them. Answers item 2.2 of the Dr. Liebovitz faculty
  review (22 Aug 2026): anchor each tier to clinician-authored criteria and
  require physician sign-off, rather than trusting generated triage advice.
Key functions/classes: EscalationTemplate, load_template, load_all, verify_guide
Edge cases handled:
  - An UNSIGNED template is never authoritative. See the note below.
  - A missing template is not an error; Agent 5 keeps its current behaviour.
  - Tier headers are fixed strings parsed by the UI; they are matched exactly.
Dependencies: standard library only.
Called by: dischargeiq.agents.escalation_agent (advisory today), and
  scripts/escalation_template_status.py for reporting.

WHY UNSIGNED TEMPLATES ARE INERT
--------------------------------
The whole point of this review item is that generated triage advice has no
clinician behind it. A template drafted by whoever set up the repository and
then USED as authoritative would be strictly worse than generation: it would
launder unreviewed criteria as clinician-authored and put a reassuring
"clinician-reviewed" label on exactly the same risk.

So a template only becomes authoritative when its sign-off block names a real
reviewer and a real date. Until then it is a draft FOR review, load_template
reports it as unsigned, and Agent 5 behaves exactly as it did before. Nothing
about the patient-facing output changes on the day a template file is added -
it changes on the day a physician signs it.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "escalation"

# Fixed tier headers. These strings are parsed by streamlit_app.py and the
# Flutter results screen, so they are matched exactly and never localised.
TIER_911 = "CALL 911 IMMEDIATELY"
TIER_ER = "GO TO THE ER TODAY"
TIER_DOCTOR = "CALL YOUR DOCTOR"
TIER_HEADERS = (TIER_911, TIER_ER, TIER_DOCTOR)

# A sign-off counts only when it names someone and gives a date. Bracketed
# placeholders like "[Pending - Dr. Liebovitz]" are the convention already used
# by the diagnosis templates in templates/, and must NOT read as signed.
_PLACEHOLDER = re.compile(r"^\s*\[.*\]\s*$")


@dataclass(frozen=True)
class EscalationTemplate:
    """
    One diagnosis's clinician-authored escalation criteria.

    Attributes:
        diagnosis_key: Filename stem, e.g. "heart_failure".
        tiers: Tier header -> the criteria bullets belonging to that tier.
        reviewed_by: Name from the sign-off block, or "" when unsigned.
        reviewed_date: Date from the sign-off block, or "" when unsigned.
        guideline: The guideline reference the criteria follow, if given.
        source_path: Where the template was loaded from.
    """

    diagnosis_key: str
    tiers: dict[str, list[str]]
    reviewed_by: str
    reviewed_date: str
    guideline: str
    source_path: Path

    @property
    def is_signed(self) -> bool:
        """
        True only when a named reviewer AND a date are both present.

        Both are required because either alone is ambiguous: a name with no
        date could predate any number of edits, and a date with no name is not
        attributable to anyone.
        """
        return bool(self.reviewed_by) and bool(self.reviewed_date)

    @property
    def is_authoritative(self) -> bool:
        """
        Whether this template may govern patient-facing output.

        Only signed templates are authoritative. An unsigned template is a
        draft awaiting review and must never silently shape triage advice.
        """
        return self.is_signed


def _clean_field(value: str) -> str:
    """
    Normalise a sign-off field, treating bracketed placeholders as empty.

    Args:
        value: Raw text after the field label.

    Returns:
        The trimmed value, or "" when it is a placeholder such as "[Pending]".
    """
    text = (value or "").strip()
    if not text or _PLACEHOLDER.match(text):
        return ""
    return text


def _parse(text: str, diagnosis_key: str, path: Path) -> EscalationTemplate:
    """
    Parse one template file into tier criteria plus its sign-off state.

    Args:
        text: Full markdown contents of the template.
        diagnosis_key: Filename stem used as the lookup key.
        path: Source path, retained for error messages and reporting.

    Returns:
        The parsed EscalationTemplate. Parsing never raises on missing
        sections: an incomplete template loads as unsigned, which is the safe
        state, rather than breaking the pipeline for a documentation problem.
    """
    tiers: dict[str, list[str]] = {header: [] for header in TIER_HEADERS}
    reviewed_by = reviewed_date = guideline = ""
    current: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        matched_header = next((h for h in TIER_HEADERS if line.upper().startswith(f"## {h}")), None)
        if matched_header:
            current = matched_header
            continue
        if line.startswith("## "):
            # Any other section (notes, sign-off) ends the current tier block.
            current = None

        if line.startswith("- ") and current:
            tiers[current].append(line[2:].strip())
        elif line.lower().startswith("**reviewed by:**"):
            reviewed_by = _clean_field(line.split("**", 2)[-1].lstrip(":").strip())
        elif line.lower().startswith("**date:**"):
            reviewed_date = _clean_field(line.split("**", 2)[-1].lstrip(":").strip())
        elif line.lower().startswith("**guideline reference:**"):
            guideline = _clean_field(line.split("**", 2)[-1].lstrip(":").strip())

    return EscalationTemplate(
        diagnosis_key=diagnosis_key,
        tiers=tiers,
        reviewed_by=reviewed_by,
        reviewed_date=reviewed_date,
        guideline=guideline,
        source_path=path,
    )


def load_template(diagnosis_key: str, template_dir: Path | None = None) -> EscalationTemplate | None:
    """
    Load one diagnosis's escalation template, if a file exists for it.

    Args:
        diagnosis_key: Filename stem, e.g. "heart_failure".
        template_dir: Override the template directory, for tests.

    Returns:
        The parsed template, or None when no file exists. None means Agent 5
        keeps its existing generated behaviour, which is the current baseline
        rather than a failure.
    """
    directory = template_dir or _TEMPLATE_DIR
    path = directory / f"{diagnosis_key}.md"
    if not path.exists():
        return None
    try:
        return _parse(path.read_text(encoding="utf-8"), diagnosis_key, path)
    except OSError as exc:
        # A template that cannot be read must not take the pipeline down; the
        # safe degradation is to behave as though it were absent.
        logger.warning("escalation template %s unreadable: %s", path, exc)
        return None


def load_all(template_dir: Path | None = None) -> list[EscalationTemplate]:
    """
    Load every escalation template, for status reporting.

    Args:
        template_dir: Override the template directory, for tests.

    Returns:
        All parsed templates, signed or not, sorted by diagnosis key. Files
        beginning with an underscore are format examples and are skipped.
    """
    directory = template_dir or _TEMPLATE_DIR
    if not directory.exists():
        return []
    templates = []
    for path in sorted(directory.glob("*.md")):
        if path.name.startswith("_"):
            continue
        template = load_template(path.stem, directory)
        if template:
            templates.append(template)
    return templates


def verify_guide(guide_text: str, template: EscalationTemplate) -> list[str]:
    """
    Check a generated guide against a signed template's Tier 1 criteria.

    Only demotion of life-threatening criteria is checked, deliberately. A
    guide may legitimately add document-specific symptoms and may rephrase
    anything into plain language, but a criterion the clinician placed in
    "CALL 911 IMMEDIATELY" must not end up in a lower tier or vanish. That is
    the failure with the worst consequence and the clearest definition.

    Args:
        guide_text: The full three-tier guide Agent 5 produced.
        template: A template to check against.

    Returns:
        Human-readable descriptions of each Tier 1 criterion that appears to
        have been demoted or dropped. Empty when the guide is consistent, and
        always empty for an unsigned template, which has no authority to
        enforce anything.
    """
    if not template.is_authoritative or not guide_text:
        return []

    upper = guide_text.upper()
    tier1_start = upper.find(TIER_911)
    if tier1_start < 0:
        return [f"guide is missing the '{TIER_911}' tier entirely"]

    # The Tier 1 block runs until whichever lower tier header appears next.
    ends = [upper.find(h, tier1_start + 1) for h in (TIER_ER, TIER_DOCTOR)]
    ends = [e for e in ends if e > 0]
    tier1_block = guide_text[tier1_start:min(ends)] if ends else guide_text[tier1_start:]
    tier1_lower = tier1_block.lower()

    problems = []
    for criterion in template.tiers.get(TIER_911, []):
        # Match on content words: the guide is expected to rephrase into plain
        # language, so requiring the literal criterion string would flag
        # correct output. This mirrors the omission checker in
        # scripts/corpus_accuracy_report.py.
        words = [w for w in re.findall(r"[a-z]{4,}", criterion.lower())][:6]
        if not words:
            continue
        hits = sum(1 for w in words if w in tier1_lower)
        if hits * 2 < len(words):
            problems.append(f"Tier 1 criterion not found in Tier 1: {criterion!r}")
    return problems
