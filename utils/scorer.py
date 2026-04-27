"""
File: utils/scorer.py
Owner: Deepesh Kumar
Description: Standalone Flesch-Kincaid helpers for evaluation scripts — computes FK grade,
  pass/fail against a threshold with human-readable labels, and can score raw PDF text for
  delta KPIs. Enforces a minimum character length so textstat gets enough words.
Key functions/classes: fk_score, fk_check, fk_baseline
Edge cases handled:
  - Raises ValueError when input text is empty or under ~10 characters (unreliable FK).
Dependencies: textstat (third-party only — not dischargeiq package imports).
Called by: Legacy/eval scripts; production agents use dischargeiq/utils/scorer.py instead.
"""

import textstat


def fk_score(text: str) -> float:
    """
    Compute the Flesch-Kincaid Grade Level for a given text string.

    Args:
        text: Any plain-language string output from an agent.

    Returns:
        float: FK grade level score rounded to 2 decimal places.
               A score of 6.0 means the text reads at a 6th grade level.
               Lower is simpler. Target for all DischargeIQ output is <= 6.0.

    Raises:
        ValueError: If text is empty or too short to produce a reliable score.
    """
    # Minimum length check — textstat needs enough words to compute reliably
    if not text or len(text.strip()) < 10:
        raise ValueError(
            f"Text too short to score reliably. "
            f"Got {len(text.strip()) if text else 0} characters, need at least 10."
        )

    return round(textstat.flesch_kincaid_grade(text), 2)


def fk_check(text: str, threshold: float = 6.0) -> dict:
    """
    Check whether an agent output meets the FK reading level target.

    Runs fk_score() and compares against the threshold.
    Used by all 5 agents after generating patient-facing output.

    Args:
        text: Agent output string to evaluate.
        threshold: FK grade level ceiling. Default is 6.0 per AMA guidelines.
                   Only change this if the team agrees to a different target.

    Returns:
        dict with the following keys:
            score   (float): The FK grade level score.
            passes  (bool):  True if score <= threshold, False otherwise.
            label   (str):   Human-readable result string for logging and UI display.

    Raises:
        ValueError: Propagated from fk_score() if text is too short to score.

    Example:
        >>> result = fk_check("Your heart was not pumping enough blood.")
        >>> print(result)
        {'score': 5.2, 'passes': True, 'label': 'Grade 5.2 — PASS'}
    """
    score = fk_score(text)
    passes = score <= threshold

    # Build a clear label for pipeline logs and the frontend badge
    status = "PASS" if passes else "FAIL — output too complex, prompt needs revision"
    label = f"Grade {score:.1f} — {status}"

    return {
        "score": score,
        "passes": passes,
        "label": label,
    }


def fk_baseline(raw_text: str) -> float:
    """
    Score the raw discharge document text before any agent processing.

    Used to calculate FK delta — the improvement between the original
    document reading level and the DischargeIQ output reading level.
    FK delta is a primary KPI in the evaluation framework.

    Args:
        raw_text: The raw text extracted from the discharge PDF by pdfplumber
                  before any agent processes it.

    Returns:
        float: FK grade level of the original document.
               Expected to be well above 6.0 for most hospital discharge documents.

    Raises:
        ValueError: Propagated from fk_score() if text is too short.
    """
    # Raw discharge documents are typically Grade 12-16 — far above patient reading level
    return fk_score(raw_text)
