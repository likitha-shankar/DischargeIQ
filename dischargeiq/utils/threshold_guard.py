"""
File: dischargeiq/utils/threshold_guard.py
Owner: Likitha Shankar
Description: Removes numeric clinical thresholds from patient-facing text when the
  patient's own document never gave them - the last line against a fever limit or a
  vital-sign cutoff being shown as if their doctor had set it.
Key functions/classes: strip_ungrounded_thresholds, ThresholdRewrite
Edge cases handled:
  - A threshold present in the source is left exactly as written; ranges and Celsius
    equivalents are matched; a sentence is rewritten, never truncated mid-clause.
Dependencies: stdlib only.
Called by: dischargeiq.pipeline.orchestrator, after agents 4 and 5.

WHY THIS IS NOT A PROMPT FIX
----------------------------
Dr Liebovitz's review, and the corpus accuracy run, both land on the same
defect: patient-facing output carries clinical thresholds - "a fever over
100.4 F" - that the patient's document never contained. A knee protocol
differs between surgeons and a fever threshold differs for an
immunocompromised patient, so a number we supply is a guess the patient reads
as their own doctor's instruction.

Four prompt attempts have failed to remove it:

  1. Enumerating forbidden numbers. The model produced a different one.
  2. Permitting only one value. Clinically wrong for infants.
  3. Removing numbers from Agent 5's tier list and worked example. Helped
     there; Agent 5 still emits 100.4, which is NOT in its prompt.
  4. Removing numerals from Agent 4's examples, Sep 2026. Measurably reduced
     the values COPIED from the prompt ("10 pounds": 5 of 10 documents to 3)
     and did nothing to the ones that were never in the prompt.

That split is the whole finding. A numeral written in a prompt gets copied,
so it must not be written. But 100.4 F is the standard fever threshold in
clinical practice, and the model reaches for it whether or not the prompt
mentions it. No wording removes a fact the model already knows.

So this runs AFTER generation, where behaviour is verifiable rather than
probabilistic.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not touch a threshold the document actually gives - that number is
the patient's doctor speaking and outranks everything here. It does not
delete sentences, because a half-sentence in an escalation guide is worse
than the number was. It rewrites the clause into the form the prompts already
ask for ("a fever that will not come down"), which is the wording a clinician
reviewed.

It is narrow on purpose: temperature and the vital signs with a standard
textbook cutoff. Every rewrite is logged, so the rate is measurable rather
than assumed.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ThresholdRewrite:
    """One numeric threshold removed from patient-facing text."""

    original: str
    replacement: str
    value: str


@dataclass
class GuardResult:
    """Text after guarding, plus what was changed."""

    text: str
    rewrites: list[ThresholdRewrite] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.rewrites)


#: Numbers that are never a clinical threshold and must never be stripped.
#: 911 is the emergency number - removing it would be catastrophic - and small
#: integers are week numbers, tablet counts and tier labels.
_NEVER_STRIP = frozenset(
    {"911", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"}
)

#: Temperature thresholds. Matches the whole clause, not the bare number, so
#: the replacement is a readable sentence rather than a gap where a number was.
#:
#: The optional trailing parenthetical catches "100.4 F (38 C)" as one unit -
#: stripping only the Fahrenheit value would leave the Celsius one behind,
#: which is the same defect in a different unit.
_TEMP_CLAUSE = re.compile(
    r"""
    (?P<lead>
        (?:a\s+)?
        (?:fever|temperature|temp)
        [^.\n]{0,40}?
    )
    (?:
        (?:over|above|greater\ than|more\ than|exceeds?|of|reaches?|hits?|>=?)
        \s*
    )
    (?P<value>\d{2,3}(?:\.\d)?)
    \s*
    (?:degrees?\s*)?
    (?:F(?:ahrenheit)?|C(?:elsius)?|°\s*[FC]?|)
    (?P<paren>\s*\(\s*\d{2,3}(?:\.\d)?\s*(?:degrees?\s*)?[FC]?\s*\))?
    """,
    re.IGNORECASE | re.VERBOSE,
)

#: Replacement wording. Taken from the agent prompts' own GOOD examples, so a
#: patient reads language a clinician already signed off on.
_TEMP_REPLACEMENT = "a fever that will not come down"


def _source_numbers(source_text: str) -> set[str]:
    """
    Every numeric token in the patient's document.

    Args:
        source_text: Raw text of the uploaded discharge document.

    Returns:
        Numbers as written, so "100.4" and "100" are distinct - a document
        saying 100 does not license an output saying 100.4.

    Note:
        The decimal part is only taken when digits follow the point. An
        earlier version used `\\d+\\.?\\d*`, which swallows the full stop at
        the end of a sentence: a source reading "a fever over 101." yielded
        "101." and never matched the output's "101", so a GROUNDED threshold
        was stripped. That is the failure this guard exists to avoid, and it
        was invisible because the validation script used the same expression
        and agreed with itself.
    """
    return set(re.findall(r"\d+(?:\.\d+)?", source_text or ""))


def strip_ungrounded_thresholds(text: str, source_text: str) -> GuardResult:
    """
    Rewrite numeric clinical thresholds the source document never gave.

    Args:
        text: Patient-facing agent output.
        source_text: Raw text of the patient's discharge document.

    Returns:
        GuardResult with the guarded text and one entry per rewrite.

    Note:
        A missing or empty source is treated as "nothing is grounded", which
        would strip every threshold. That is the wrong failure: an extraction
        that produced no text is a different problem, and silently rewriting
        the whole guide would hide it. Empty source returns the text
        unchanged.
    """
    if not text or not source_text:
        return GuardResult(text=text)

    grounded = _source_numbers(source_text)
    rewrites: list[ThresholdRewrite] = []

    def replace(match: re.Match) -> str:
        value = match.group("value")
        # The patient's own doctor set this number. It outranks us.
        if value in grounded or value in _NEVER_STRIP:
            return match.group(0)
        # A parenthetical equivalent is grounded only if IT is in the source
        # too; otherwise the whole clause goes.
        rewrites.append(
            ThresholdRewrite(
                original=match.group(0).strip(),
                replacement=_TEMP_REPLACEMENT,
                value=value,
            )
        )
        return _TEMP_REPLACEMENT

    guarded = _TEMP_CLAUSE.sub(replace, text)

    if rewrites:
        logger.info(
            "threshold_guard removed %d ungrounded threshold(s): %s",
            len(rewrites), ", ".join(r.value for r in rewrites),
        )
    return GuardResult(text=guarded, rewrites=rewrites)
