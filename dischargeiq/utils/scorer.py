"""
Flesch-Kincaid readability scorer for DischargeIQ.

Every agent text output must pass through fk_check() before being returned.
Target: FK grade <= 6.0 (6th grade reading level).

Depends on: textstat.
"""

import textstat


def fk_score(text: str) -> float:
    """
    Compute the Flesch-Kincaid grade level of the given text.

    Args:
        text: Plain-text output from any agent.

    Returns:
        float: The FK grade level (lower is simpler).
    """
    return textstat.flesch_kincaid_grade(text)


def fk_check(text: str, threshold: float = 6.0) -> dict:
    """
    Check whether the text meets the readability threshold.

    Args:
        text: Plain-text output from any agent.
        threshold: Maximum acceptable FK grade (default 6.0).

    Returns:
        dict with keys:
            - fk_grade (float): Rounded FK score.
            - passes (bool): True if score <= threshold.
            - threshold (float): The threshold used.
    """
    score = fk_score(text)
    return {
        "fk_grade": round(score, 2),
        "passes": score <= threshold,
        "threshold": threshold,
    }
