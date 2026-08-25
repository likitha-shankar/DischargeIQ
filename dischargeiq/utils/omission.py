"""
File: dischargeiq/utils/omission.py
Owner: Likitha Shankar
Description: Detects content the extraction captured that never reached the
  patient. Errors of omission are the dominant failure mode and are invisible
  to the patient: a dropped medication or warning sign yields a clean,
  confident, incorrect document. Answers item 2.5 of the Dr. Liebovitz faculty
  review (22 Aug 2026).
Key functions/classes: omitted_medications, omitted_red_flags
Edge cases handled:
  - Plain-language rephrasing ("edema" -> "swelling") is NOT an omission; that
    translation is the product working.
  - Plurals and comparison filler ("greater than") do not create false hits.
  - A substituted threshold ("fever over 101" for a document that said 100.5)
    IS an omission, and is checked pass/fail rather than by vote.
Dependencies: standard library only.
Called by: scripts/corpus_accuracy_report.py, dischargeiq.tests.test_omission_recall

Extracted from corpus_accuracy_report.py on 25 Aug 2026: that script had grown
past the 500-line limit and this logic is useful at runtime, not only offline.
Its sibling, the fabrication check that looks the other way, lives in
dischargeiq/utils/grounding.py.
"""

import re

def omitted_medications(output: dict) -> list[str]:
    """
    Medications the extraction found that never reach the patient-facing text.

    Errors of omission are the dominant failure mode and are invisible to the
    patient: a dropped drug yields a clean, confident, incorrect document
    (Liebovitz review, item 2.5). This measures the leg of that risk we own
    completely - Agent 1 extracted the drug, and Agent 3 did not explain it.
    No annotation is needed, because the extraction record IS the ground truth
    for this comparison.

    The source-to-extraction leg is the other half of omission risk and cannot
    be measured without the clinician-annotated gold standard (review item
    3.5). Do not read this number as total omission.

    Args:
        output: One pipeline output dict.

    Returns:
        Names of extracted medications absent from `medication_rationale`.
    """
    rationale = str(output.get("medication_rationale") or "").lower()
    if not rationale:
        return []
    missing = []
    for med in (output.get("extraction") or {}).get("medications") or []:
        name = str(med.get("name") or "").strip().lower()
        # Match on the first word, consistent with ungrounded_medications():
        # "Furosemide 40mg tablet" is covered if the text says "furosemide".
        head = re.split(r"[\s,(/]", name)[0] if name else ""
        if len(head) >= 4 and head not in rationale:
            missing.append(str(med.get("name")))
    return missing


# Clinical term -> the plain-language words Agent 5 is EXPECTED to use instead.
# Without this, the omission check penalises the system for doing its job:
# "edema" rendered as "swelling in arms or legs" is a correct translation, and
# an exact-match test scores it as a dropped warning sign. Verified against
# mtsamples_068 on 25 Aug 2026, where exactly that produced a false positive.
_PLAIN_LANGUAGE = {
    "edema": ("swell",),
    "dyspnea": ("breath", "breathing"),
    "pyrexia": ("fever", "temperature"),
    "febrile": ("fever", "temperature"),
    "emesis": ("vomit", "throw"),
    "syncope": ("faint", "pass out"),
    "erythema": ("redness", "red"),
    "pruritus": ("itch",),
    "purulent": ("pus",),
    "hematuria": ("blood",),
    "tachycardia": ("fast heart", "racing"),
    "hypotension": ("low blood pressure", "dizzy"),
    "hypertension": ("high blood pressure",),
    "dysuria": ("burning", "urinate"),
    "melena": ("black stool", "blood"),
}


# Comparison and filler words that carry no clinical content. A plain-language
# rewrite legitimately turns "fever greater than 100.5" into "fever over
# 100.5", so counting "greater" and "than" as content marks a correct guide as
# an omission. Verified on mtsamples_054 and _064 on 25 Aug 2026.
_FILLER_WORDS = frozenset({
    "greater", "than", "more", "less", "over", "above", "below", "under",
    "that", "this", "with", "your", "from", "have", "when", "which", "then",
    "any", "and", "the", "for", "not", "also", "some", "such", "very",
})


def _content_tokens(phrase: str) -> list[str]:
    """
    The parts of a warning-sign phrase that actually have to survive.

    Two kinds of token count: clinical words of four letters or more, and any
    number. Numbers are included deliberately - a threshold is the most
    dangerous thing to get wrong, so "fever over 100.5" rendered as "fever
    over 101" must register as a failure rather than a match on the word
    "fever" alone.

    Args:
        phrase: One extracted red-flag symptom, lowercased.

    Returns:
        Content tokens, filler and short connectives removed.
    """
    words = [w for w in re.findall(r"[a-z]{4,}", phrase) if w not in _FILLER_WORDS]
    numbers = re.findall(r"\d+(?:\.\d+)?", phrase)
    return words + numbers


def _word_covered(word: str, guide: str) -> bool:
    """
    Whether one content word from a warning sign appears in the guide.

    Matching accounts for the two ways a correct guide legitimately differs
    from the extracted phrase:

      PLURALS         - "fevers" against a guide that says "fever". A bare
                        substring test misses this and reports a false
                        omission (verified on mtsamples_019 and _027).
      PLAIN LANGUAGE  - "edema" against "swelling", which is the translation
                        this product exists to perform.

    Args:
        word: A single lowercase content word from the extracted symptom.
        guide: The lowercased escalation guide text.

    Returns:
        True if the word, its singular form, or an accepted plain-language
        equivalent appears in the guide.
    """
    if word in guide:
        return True
    # Cheap singularisation. Real stemming is not worth a dependency here:
    # the inputs are short clinical noun phrases, not free prose.
    for suffix in ("ies", "es", "s"):
        if word.endswith(suffix):
            stem = word[: -len(suffix)]
            if suffix == "ies":
                stem += "y"
            if len(stem) >= 3 and stem in guide:
                return True
    return any(alt in guide for alt in _PLAIN_LANGUAGE.get(word, ()))


def omitted_red_flags(output: dict) -> list[str]:
    """
    Warning signs the extraction found that the escalation guide never mentions.

    Agent 5 is the safety-critical output. A red flag the document listed and
    the guide drops is the highest-consequence omission in the system, so it
    is counted separately from medications rather than folded into one number.

    Matching is deliberately generous: a symptom counts as covered when at
    least half its content words appear in the guide, because Agent 5 is
    expected to rephrase ("shortness of breath" -> "trouble breathing"). A
    generous test that still finds omissions is stronger evidence than a
    strict test that finds them everywhere.

    Args:
        output: One pipeline output dict.

    Returns:
        Extracted red-flag phrases with no apparent coverage in the guide.
    """
    guide = str(output.get("escalation_guide") or "").lower()
    if not guide:
        return []
    missing = []
    for symptom in (output.get("extraction") or {}).get("red_flag_symptoms") or []:
        phrase = str(symptom or "").lower()
        # Content tokens only: short connectives would match almost any text
        # and make every symptom look covered.
        words = _content_tokens(phrase)
        if not words:
            continue

        # A threshold is pass/fail, never a vote. "fever greater than 100.5"
        # rendered as "fever over 101" would otherwise score as covered on the
        # word "fever" alone, which is the single most dangerous way this
        # check could lie: a substituted threshold reads as correct to the
        # patient and is wrong for their case.
        numbers = [w for w in words if w[0].isdigit()]
        if any(number not in guide for number in numbers):
            missing.append(str(symptom))
            continue

        prose = [w for w in words if not w[0].isdigit()]
        if not prose:
            continue
        hits = sum(1 for w in prose if _word_covered(w, guide))
        if hits * 2 < len(prose):
            missing.append(str(symptom))
    return missing
