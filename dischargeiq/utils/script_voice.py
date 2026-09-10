"""
File: dischargeiq/utils/script_voice.py
Owner: Likitha Shankar
Description: Finds collective phrasing in an audio script - "most people feel
  better in a week" - where the patient's own plan should be the subject.
Key functions/classes: collective_claims, CollectiveClaim
Edge cases handled:
  - A collective phrase quoting the patient's own document is still flagged,
    because the ATTRIBUTION is the defect, not the fact.
  - "You" and "your plan" phrasing is never flagged.
Dependencies: standard library only.
Called by: scripts/build_condition_audio.py (refuses to ship), and the
  per-case audio path (logs, non-fatal).

WHY
---
Frank Naeymi-Rad, 10 Sep 2026: emphasise patient-specific instructions over
collective language, to keep the audio accurate and liability-safe.

The live example that prompted it, from `dischargeiq/media/surgical.script.txt`:

    Sam: Most people feel better in one to two weeks.

Two different sentences are hiding in that. "Your plan says you should feel
better in one to two weeks" reports what a clinician wrote for this patient.
"Most people feel better in one to two weeks" is a general medical claim about
a population, delivered in a calm voice to someone who has just had surgery -
and if their recovery is slower, the app has told them they are behind.

The fact may be identical. The speaker is not. This checks the speaker.

WHY A CHECK AND NOT JUST A PROMPT RULE
--------------------------------------
The same reason `threshold_guard` exists. Four prompt revisions failed to stop
agents 4 and 5 emitting invented fever thresholds, because no wording removes
a habit the model already has. The prompt rule is worth having and is not
worth trusting, so behaviour is verified after generation where it can be
measured.
"""

import re
from dataclasses import dataclass

#: Phrases that make a population the subject of a clinical claim.
#:
#: Each is a real pattern seen in generated scripts or in the agent outputs
#: they are built from. Kept explicit rather than clever: a regex broad enough
#: to catch every phrasing would also catch "your plan", and a check that
#: fires on correct output is a check people switch off.
#: Two branches, because they need different boundary handling. The first is
#: word-bounded on both sides; the second ends in a comma, and `,\b` can never
#: match - a word boundary needs a word character next to it, and a comma is
#: followed by a space. That branch silently matched nothing until a test
#: asked it to.
#:
#: The apostrophe class covers straight and curly: models emit both, and the
#: chat grounding detector already carries the same fix for the same reason.
_COLLECTIVE = re.compile(
    r"\b("
    r"most people|many people|some people|other people|"
    r"people (?:usually|often|typically|generally|normally|tend to)|"
    r"patients (?:usually|often|typically|generally|normally|tend to)|"
    r"everyone|anybody|most patients|many patients|"
    r"it(?:\s+is|['’]s)\s+(?:common|normal|usual|typical)"
    r")\b"
    r"|"
    r"\b(?:usually|typically|generally|normally),",
    re.IGNORECASE,
)

#: Phrasing that makes the patient or their document the subject. A sentence
#: carrying one of these is talking to the listener about their own plan, so a
#: collective word inside it is describing something else.
_PATIENT_VOICE = re.compile(
    r"\b(your plan|your summary|your document|your care team|your doctor|"
    r"your paperwork|you were told|your notes)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CollectiveClaim:
    """One sentence speaking for a population rather than for this patient."""

    phrase: str
    sentence: str
    speaker: str


def collective_claims(script: str) -> list[CollectiveClaim]:
    """
    Every sentence in a script that states a claim about people in general.

    Args:
        script: Dialogue text, "Sam: ..." / "Alex: ..." lines, or plain prose.

    Returns:
        list[CollectiveClaim]: One entry per offending sentence, in order.
        Empty when the script speaks to the patient throughout.

    Note:
        A sentence that already anchors to the patient's own plan is not
        flagged even when it contains a collective word - "Your plan says most
        of your medicines continue" is about this patient's medicines. The
        target is the SUBJECT of the claim, not the vocabulary.
    """
    if not script:
        return []

    found: list[CollectiveClaim] = []
    for raw_line in script.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        speaker = ""
        match = re.match(r"^(\w+)\s*:\s*(.*)$", line)
        if match:
            speaker, line = match.group(1), match.group(2)
        # Sentence-level, so one offending clause does not condemn a whole
        # speaker line and a reviewer sees exactly what to rewrite.
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            sentence = sentence.strip()
            if not sentence:
                continue
            hit = _COLLECTIVE.search(sentence)
            if not hit:
                continue
            if _PATIENT_VOICE.search(sentence):
                continue
            found.append(CollectiveClaim(
                phrase=hit.group(0), sentence=sentence, speaker=speaker))
    return found


def describe(claims: list[CollectiveClaim]) -> str:
    """One human-readable line per claim, for a log or a refusal message."""
    return "; ".join(
        f"{c.speaker or 'script'}: {c.phrase!r} in {c.sentence!r}"
        for c in claims
    )
