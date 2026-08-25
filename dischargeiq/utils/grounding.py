"""
File: dischargeiq/utils/grounding.py
Owner: Likitha Shankar
Description: Post-hoc grounding verifier. Checks that every clinical entity and
  number in a patient-facing agent output is traceable to the Agent 1 extraction
  record, turning "no fabrication" from a prompt instruction into a checkable
  property. Answers item 3.2 of the Dr. Liebovitz faculty review (22 Aug 2026).
Key functions/classes: verify_output, GroundingFinding, GroundingReport
Edge cases handled:
  - Plain-language rephrasing ("edema" -> "swelling") is not a violation.
  - Ordinary counts (week numbers, 911, "2 to 4 weeks") are not clinical claims.
  - Numbers the PROMPTS supply (fever thresholds) are classified separately from
    numbers the model invents, because they need different fixes by different people.
Dependencies: none beyond the standard library.
Called by: report-only callers today. NOT wired into the pipeline as a hard
  failure - see the module note below before doing that.

WHY THIS IS REPORT-ONLY TODAY
-----------------------------
The review asks for a hard failure on mismatch, and that is the right end
state. It is not the right first step. On 25 Aug 2026 the sibling omission
checker in scripts/corpus_accuracy_report.py reported six violations on its
first run against the real corpus and every single one was a false positive -
plurals, dropped filler words, and one case where Agent 5 had correctly
translated "edema" into "swelling in arms or legs". A hard gate wired in at
that quality would have failed every document and taught everyone to bypass it.

So: measure the false-positive rate on the corpus first, tune, and only then
promote to enforcement. A gate that cannot be trusted is worse than no gate,
because it launders a rubber stamp as a guarantee.
"""

import re
from dataclasses import dataclass, field

# Numbers that are ordinary language rather than clinical claims. "Week 1",
# "call 911", "2 to 4 weeks" are not invented dosages. Kept deliberately in
# sync with scripts/corpus_accuracy_report.py, which measures the same thing
# offline over the whole corpus.
_BENIGN_NUMBERS = frozenset(
    {"911", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "24"}
)

# Numeric values that genuinely come from the agent PROMPTS rather than from
# any patient's document. These are defensible as general patient education and
# indefensible when shown as if the patient's own paperwork said so, so they are
# classified separately: the fix is a clinical decision about attribution rather
# than a code bug.
#
# Kept to what agent5_system_prompt.txt ACTUALLY contains, verified 25 Aug 2026.
# The set previously also held 100.4, 101.5 and 102, none of which appear in any
# prompt - so genuinely invented thresholds were being excused as "the prompt
# said so" and hidden from invented_findings. A classifier that quietly
# downgrades real findings is worse than no classifier, because the count looks
# clean for the wrong reason.
_PROMPT_SUPPLIED_THRESHOLDS = frozenset({"101", "38.5"})

# Sections checked, mapped to the agent that produces them.
_NARRATIVE_FIELDS = {
    "diagnosis_explanation": "agent2",
    "medication_rationale": "agent3",
    "recovery_trajectory": "agent4",
    "escalation_guide": "agent5",
}


@dataclass(frozen=True)
class GroundingFinding:
    """
    One piece of output content with no counterpart in the source record.

    Attributes:
        agent: Which agent produced the section, e.g. "agent4".
        field: The PipelineResponse field name the finding came from.
        kind: "medication" or "number".
        value: The specific token that could not be grounded.
        category: For numbers - "prompt_threshold", "invented", or "unknown".
            Medications are always "invented": Agent 1's contract forbids
            inventing a drug name, so there is no benign class.
    """

    agent: str
    field: str
    kind: str
    value: str
    category: str


@dataclass
class GroundingReport:
    """
    The result of verifying one pipeline output against its source.

    Attributes:
        findings: Every ungrounded item found.
        checked_fields: Narrative fields that were actually examined.
        source_available: False when no source text was supplied, in which case
            an empty findings list means "not checked", NOT "clean".
    """

    findings: list[GroundingFinding] = field(default_factory=list)
    checked_fields: list[str] = field(default_factory=list)
    source_available: bool = True

    @property
    def is_clean(self) -> bool:
        """
        True only when the output was checked and nothing was ungrounded.

        An unchecked output is never clean. Conflating "we did not look" with
        "we looked and it was fine" is the specific way a verifier turns into
        a rubber stamp.
        """
        return self.source_available and not self.findings

    @property
    def invented_findings(self) -> list[GroundingFinding]:
        """Findings that are defects in this system, excluding prompt thresholds."""
        return [f for f in self.findings if f.category != "prompt_threshold"]


def _medication_head(name: str) -> str:
    """
    The comparable part of a medication name.

    "Furosemide 40mg tablet" is grounded if the source says "furosemide", and
    brand/generic spacing varies, so only the first token is compared.

    Args:
        name: Raw medication name from the extraction record.

    Returns:
        The lowercased leading token, or "" when there is nothing to compare.
    """
    cleaned = str(name or "").strip().lower()
    return re.split(r"[\s,(/]", cleaned)[0] if cleaned else ""


def _classify_number(value: str) -> str:
    """
    Say what kind of ungrounded number this is, because the fixes differ.

    Args:
        value: The numeric token as it appeared in the output.

    Returns:
        "prompt_threshold" when it is standard clinical guidance the prompts
        supply, otherwise "invented".
    """
    return "prompt_threshold" if value in _PROMPT_SUPPLIED_THRESHOLDS else "invented"


def verify_output(output: dict, source_text: str) -> GroundingReport:
    """
    Check one pipeline output against the document it claims to describe.

    Every medication name and every clinically meaningful number in the
    patient-facing sections must appear in the source. This makes "no
    fabrication" checkable after the fact rather than merely instructed, and it
    is what would make citation chips trustworthy: a chip can only point at
    source text that actually exists.

    Args:
        output: A PipelineResponse-shaped dict.
        source_text: Raw text of the source document. May be empty, in which
            case the report is marked unchecked rather than clean.

    Returns:
        GroundingReport describing everything that could not be grounded.

    Note:
        Report-only by design today. See the module docstring before wiring
        this into the pipeline as a hard failure - the false-positive rate has
        to be measured on the corpus first.
    """
    if not source_text:
        # No source means no verdict. Callers must treat this as "unknown",
        # which is why source_available gates is_clean.
        return GroundingReport(source_available=False)

    source = source_text.lower()
    report = GroundingReport()

    extraction = output.get("extraction") or {}
    for med in extraction.get("medications") or []:
        head = _medication_head(med.get("name"))
        # Short tokens match too much to be evidence of anything.
        if len(head) >= 4 and head not in source:
            report.findings.append(
                GroundingFinding(
                    agent="agent1",
                    field="extraction.medications",
                    kind="medication",
                    value=str(med.get("name")),
                    category="invented",
                )
            )

    for field_name, agent in _NARRATIVE_FIELDS.items():
        text = str(output.get(field_name) or "")
        if not text:
            continue
        report.checked_fields.append(field_name)
        seen: set[str] = set()
        for number in re.findall(r"\b\d+(?:\.\d+)?\b", text):
            if number in _BENIGN_NUMBERS or number in seen:
                continue
            seen.add(number)
            if number not in source:
                report.findings.append(
                    GroundingFinding(
                        agent=agent,
                        field=field_name,
                        kind="number",
                        value=number,
                        category=_classify_number(number),
                    )
                )

    return report
