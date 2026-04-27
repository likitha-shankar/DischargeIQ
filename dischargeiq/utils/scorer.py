"""
File: dischargeiq/utils/scorer.py
Owner: Likitha Shankar
Description: Production FK scoring for agent outputs — wraps textstat Flesch-Kincaid
  grade and returns fk_grade plus passes flag against a default 6.0 threshold used across
  Agents 2–5 (and related logging).
Key functions/classes: fk_score, fk_check
Edge cases handled:
  - None documented (short or empty text may yield extreme scores; callers should validate).
Dependencies: textstat (external).
Called by: dischargeiq.agents.diagnosis_agent, medication_agent, recovery_agent,
  escalation_agent, and any code importing fk_check for pipeline outputs.
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
