"""
File: dischargeiq/utils/scorer.py
Owner: Likitha Shankar
Description: Production FK scoring and centralised FK CSV logging for all agents.
  fk_score/fk_check compute and validate Flesch-Kincaid grade; log_fk_score appends
  one row to evaluation/fk_log.csv under a threading.Lock so concurrent agents
  (or concurrent pipeline runs) cannot interleave header rows or corrupt the CSV.
Key functions/classes: fk_score, fk_check, log_fk_score
Edge cases handled:
  - Empty/whitespace text raises ValueError before textstat is called.
  - OSError on CSV write is logged and swallowed (non-critical path).
  - _fk_log_lock serialises all writers - safe under asyncio.gather parallelism.
Dependencies: textstat (external); csv, logging, threading, pathlib (stdlib).
Called by: all dischargeiq.agents.* (via log_fk_score) and any code importing fk_check.
"""

import csv
import logging
import threading
from pathlib import Path

import textstat

logger = logging.getLogger(__name__)

_FK_LOG_PATH = Path(__file__).parent.parent / "evaluation" / "fk_log.csv"

# Serialises all concurrent writers. Prevents two parallel agents from both
# seeing _FK_LOG_PATH.exists() == False and writing duplicate header rows.
_fk_log_lock = threading.Lock()


def fk_score(text: str) -> float:
    """
    Compute the Flesch-Kincaid grade level of the given text.

    Args:
        text: Plain-text output from any agent.

    Returns:
        float: The FK grade level (lower is simpler).

    Raises:
        ValueError: If text is None, empty, or whitespace-only - textstat
            returns undefined/extreme values for degenerate input.
    """
    if not text or not text.strip():
        raise ValueError(
            "Cannot score empty or whitespace-only text. "
            "Ensure the agent produced output before calling fk_score()."
        )
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


def log_fk_score(document_id: str, agent: str, fk_result: dict) -> None:
    """
    Append one FK score row to dischargeiq/evaluation/fk_log.csv.

    Thread-safe: _fk_log_lock prevents concurrent parallel-agent writes from
    interleaving header rows or producing a malformed CSV. The directory
    creation is outside the lock (mkdir is idempotent; no race risk there).

    Args:
        document_id: Source document label (use os.path.basename of the PDF path
                     for readable logs - not the full /tmp/... path).
        agent:       Agent key string, e.g. "agent3_medication".
        fk_result:   Dict from fk_check() - keys: fk_grade, passes, threshold.
    """
    _FK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _fk_log_lock:
        write_header = not _FK_LOG_PATH.exists()
        try:
            with open(_FK_LOG_PATH, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["document_id", "agent", "fk_grade", "passes", "threshold"],
                )
                if write_header:
                    writer.writeheader()
                writer.writerow({
                    "document_id": document_id,
                    "agent": agent,
                    "fk_grade": fk_result["fk_grade"],
                    "passes": fk_result["passes"],
                    "threshold": fk_result["threshold"],
                })
        except OSError as exc:
            logger.warning("Could not write FK log for '%s': %s", document_id, exc)
