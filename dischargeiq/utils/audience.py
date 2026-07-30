"""
utils/audience.py

Determines who the patient-facing agents are writing TO.

Every agent output is written in second person ("Your ears have an infection").
That is correct for an adult patient and wrong for a 10-month-old, whose
discharge summary is read by a parent. Agent 1's locked extraction schema has
no age field, so the age is recovered from the raw document text here and
passed to the agents as an explicit audience instruction.

Deliberately conservative: anything it cannot classify with confidence returns
PATIENT, which is the pre-existing behaviour. A missed pediatric case reads
slightly oddly; a false pediatric hit would tell an adult about "your child's"
condition, which is worse.

Used by: dischargeiq/pipeline/orchestrator.py (derives once per document)
Consumed by: dischargeiq/agents/diagnosis_agent.py (Agent 2)
"""

import re

# Audience values passed to the agents. Kept as plain strings rather than an
# Enum because they are interpolated straight into an LLM user message.
AUDIENCE_PATIENT = "patient"
AUDIENCE_CAREGIVER = "caregiver"

# Only the first stretch of a discharge document is searched. The patient's own
# age is stated early, in the history of present illness ("The patient is a
# 10-month-old male"). Later mentions are usually somebody else - a family
# history note, or a child described in the social history - and matching those
# would misclassify an adult's document.
_AGE_SEARCH_WINDOW_CHARS = 1500

# Below this age the summary is written for whoever is caring for the patient.
# Set at 12 because adolescents commonly read their own discharge instructions,
# and telling a 16-year-old about "your child's condition" is its own error.
# Tunable: this is a communication judgement, not a clinical threshold.
_CAREGIVER_AGE_MAX = 12

# "10-month-old male", "3 week old", "2-day-old", "68-year-old woman".
# Hyphens are optional because dictated text varies.
_AGE_PATTERN = re.compile(
    r"(\d{1,3})[\s-]*(day|week|month|year)[\s-]*old",
    flags=re.IGNORECASE,
)

# Explicit words that identify an infant with no number attached at all.
_INFANT_WORDS = re.compile(
    r"\bnewborn\b|\bneonate\b|\bneonatal\b|\binfant\b",
    flags=re.IGNORECASE,
)


def _age_in_years(quantity: int, unit: str) -> float:
    """
    Convert a matched age phrase into years.

    Args:
        quantity: The numeric portion of the age phrase.
        unit: One of day / week / month / year, case-insensitive.

    Returns:
        float: Age expressed in years. Sub-year units become fractions, so a
               "10-month-old" is 0.83 rather than being rounded away to 0.
    """
    unit = unit.lower()
    if unit == "year":
        return float(quantity)
    if unit == "month":
        return quantity / 12.0
    if unit == "week":
        return quantity / 52.0
    return quantity / 365.0  # day


def detect_audience(document_text: str) -> str:
    """
    Decide whether agent output should address the patient or their caregiver.

    Scans only the opening of the document for the first age phrase, which in a
    discharge summary is the patient's own age. Falls back to explicit infant
    vocabulary when no numeric age is present.

    Args:
        document_text: Raw text of the discharge document, as produced by
                       dischargeiq.ingest.extract_document_text().

    Returns:
        str: AUDIENCE_CAREGIVER when the patient is a young child, otherwise
             AUDIENCE_PATIENT. Unparseable or missing text yields
             AUDIENCE_PATIENT, preserving the previous behaviour.
    """
    if not document_text:
        return AUDIENCE_PATIENT

    window = document_text[:_AGE_SEARCH_WINDOW_CHARS]

    match = _AGE_PATTERN.search(window)
    if match:
        quantity = int(match.group(1))
        # An implausible age means the phrase was something other than the
        # patient's age; do not guess from it.
        age_years = _age_in_years(quantity, match.group(2))
        if age_years > 130:
            return AUDIENCE_PATIENT
        return (
            AUDIENCE_CAREGIVER if age_years < _CAREGIVER_AGE_MAX else AUDIENCE_PATIENT
        )

    # No numeric age. "Newborn male discharged in stable condition" still needs
    # the caregiver voice.
    if _INFANT_WORDS.search(window):
        return AUDIENCE_CAREGIVER

    return AUDIENCE_PATIENT


def audience_instruction(audience: str) -> str:
    """
    Render the audience as an instruction line for an agent's user message.

    Args:
        audience: AUDIENCE_PATIENT or AUDIENCE_CAREGIVER.

    Returns:
        str: One line to append to the user message. Empty string for the
             patient audience, since the system prompt already defaults to
             addressing the patient directly and repeating it wastes tokens.
    """
    if audience == AUDIENCE_CAREGIVER:
        return (
            "AUDIENCE: The patient is a young child. Write to the parent or "
            "caregiver who is reading this, not to the patient. Say "
            "\"your child\" and never \"you\" when referring to the person "
            "who was treated."
        )
    return ""
