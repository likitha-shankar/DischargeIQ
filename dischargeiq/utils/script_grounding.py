"""
File: dischargeiq/utils/script_grounding.py
Owner: Likitha Shankar
Description: Checks a generated TTS dialogue script against the pipeline payload it
  was written from - the last unguarded place a fabrication reaches a patient.
Key functions/classes: verify_script_grounding, ScriptGroundingReport
Edge cases handled:
  - Plain-language synonyms are accepted (hemoptysis -> "cough up blood"); an empty
    payload disables checking rather than condemning everything.
Dependencies: stdlib only.
Called by: dischargeiq.utils.case_audio, which retries once on a failed script.

WHY THIS IS A CHECK AND NOT ANOTHER PROMPT RULE
-----------------------------------------------
`tts_script_prompt.txt` already says, in terms, that adding a warning sign the
care plan does not contain is forbidden. Prompt rules of exactly that shape
have failed twice in this codebase already, so the rule alone is not evidence
the script is grounded.

HONEST PROVENANCE. This module was written on 9 Sep 2026 after what looked
like a live example - a script naming "leg spasms" that seemed absent from the
source. It was NOT a fabrication. The escalation guide and the source document
both say "leg muscle spasms"; the search was for the two-word phrase "leg
spasm", which does not substring-match, and a failed match was read as an
invention. The checker itself made the same mistake in its first version and
is keyed on the bare token "spasm" because of it.

The module is kept because the RISK is real and unguarded, not because that
example was: agent text is checked by the threshold guard and the extraction
contract, and the audio script was checked by nothing. Two other instances of
this exact pattern are documented and were real:

  Invented fever thresholds. Four prompt attempts failed; a deterministic
  post-generation guard fixed it (`utils/threshold_guard.py`).

  Copied worked examples. Agent 4 reproduced its own BAD example verbatim,
  and the GOOD example leaked hardest of all.

The lesson each time is the same: a rule the model already knows how to break
is not fixed by rewording it. So this verifies AFTER generation.

WHY IT REJECTS RATHER THAN REWRITES
-----------------------------------
The threshold guard rewrites, because a temperature clause has one safe
replacement wording that a clinician has already approved. A dialogue script
does not: there is no safe generic sentence to swap in, and editing free-form
speech risks leaving a half-sentence in the middle of emergency guidance.

So a failed script is regenerated once and, failing that, refused. Audio is
optional by contract - `POST /media/case` returning an error is handled by
every client as "no player, read the text" - so refusing costs a patient
nothing. Shipping an invented symptom costs them a great deal.
"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ScriptGroundingReport:
    """What a script claims that its payload does not support."""

    ungrounded_symptoms: list[str] = field(default_factory=list)

    @property
    def is_grounded(self) -> bool:
        return not self.ungrounded_symptoms


#: Symptom phrases a script may use that are worth checking, paired with the
#: wording the pipeline is likely to carry. Deliberately a SMALL list of
#: high-consequence, unambiguous symptoms rather than an attempt at coverage:
#: a broad matcher on free-form speech produces false rejections, and a false
#: rejection silently removes a patient's audio.
_CHECKED_SYMPTOMS: dict[str, tuple[str, ...]] = {
    # Keyed on the bare word, not "leg spasm". The real regression said "leg
    # MUSCLE spasms", which a substring match on "leg spasm" misses entirely -
    # the same fabrication two words apart. Match the distinctive token.
    "spasm": ("spasm", "cramp"),
    "calf pain": ("calf",),
    "chest pain": ("chest pain", "chest"),
    "cough up blood": ("hemoptysis", "cough up blood", "coughing blood",
                       "blood in your cough", "coughing up blood"),
    "swelling in your legs": ("swelling", "edema"),
    "blurred vision": ("blurred vision", "vision"),
    "confusion": ("confusion", "confused"),
    "fainting": ("faint", "syncope", "passed out"),
    "cramp": ("cramp", "spasm"),
    "seizure": ("seizure", "convulsion"),
    "rash": ("rash",),
    "vomiting blood": ("vomiting blood", "hematemesis", "vomit blood"),
    "black stool": ("black stool", "melena", "tarry"),
}


def _payload_text(payload: dict) -> str:
    """
    Everything the pipeline produced, lowercased, as one haystack.

    A symptom is grounded if it appears ANYWHERE in the payload - extraction
    fields or agent prose. Agent 5's universal tiers are legitimate content
    the script may repeat, so "calf pain" coming from the escalation guide is
    grounded even when the source document never said it.
    """
    return str(payload).lower()


def verify_script_grounding(script: str, payload: dict) -> ScriptGroundingReport:
    """
    Find symptoms a script names that the pipeline output does not support.

    Args:
        script: The generated two-host dialogue.
        payload: The PipelineResponse dict the script was written from.

    Returns:
        A report listing ungrounded symptom phrases. Empty means grounded.

    Note:
        An empty payload disables the check. With nothing to compare against,
        every phrase would read as ungrounded and every script would be
        refused - turning a missing payload into a total audio outage rather
        than the input error it is.
    """
    if not script or not payload:
        return ScriptGroundingReport()

    haystack = _payload_text(payload)
    spoken = script.lower()
    ungrounded: list[str] = []

    for phrase, accepted in _CHECKED_SYMPTOMS.items():
        if phrase not in spoken:
            continue
        # Grounded if the payload carries the phrase itself or any of the
        # clinical forms it plausibly translates - "hemoptysis" in the
        # extraction licenses "cough up blood" in the script, which is the
        # plain-language translation this product exists to do.
        if any(term in haystack for term in accepted):
            continue
        ungrounded.append(phrase)

    if ungrounded:
        logger.warning(
            "TTS script names symptoms absent from the payload: %s",
            ", ".join(ungrounded),
        )
    return ScriptGroundingReport(ungrounded_symptoms=ungrounded)
