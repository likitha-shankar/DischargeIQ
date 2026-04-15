"""
agents/diagnosis_agent.py

Agent 2 — Diagnosis Explanation Agent (DIS-8).
Owner: Deepesh Kumar | Sprint 1 Week 2

Consumes ExtractionOutput.primary_diagnosis (and secondary_diagnoses,
procedures_performed) from Agent 1 and produces a plain-language paragraph
explaining the diagnosis at a 6th grade Flesch-Kincaid reading level.

Every output is scored with utils.scorer.fk_check() before return.
FK scores are logged to dischargeiq/evaluation/fk_log.csv automatically.

Data contract:
    Input:  dischargeiq.models.extraction.ExtractionOutput (from Agent 1)
    Output: dict with keys:
                text     (str)   — plain-language explanation paragraph
                fk_grade (float) — FK grade level of the output
                passes   (bool)  — True if fk_grade <= 6.0

Dependencies:
    - anthropic          (pip install anthropic)
    - ANTHROPIC_API_KEY  set in .env or environment
    - dischargeiq.models.extraction.ExtractionOutput
    - dischargeiq.utils.scorer.fk_check
    - dischargeiq/prompts/agent2_system_prompt.txt

BLOCKED BY: DIS-5 (Agent 1) must be Done before this runs in production.
"""

import csv
import logging
import os
from pathlib import Path

import anthropic
from anthropic import APIError

from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.utils.scorer import fk_check

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

# Allow model override via env var so team can swap without touching code
_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
_MAX_TOKENS = 500

# Paths resolved relative to this file
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_FK_LOG_PATH = Path(__file__).parent.parent / "evaluation" / "fk_log.csv"

# Initialise Anthropic client once at module load
_client = anthropic.Anthropic()


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_system_prompt() -> str:
    """
    Load the Agent 2 system prompt from dischargeiq/prompts/agent2_system_prompt.txt.

    Returns:
        str: The full system prompt text.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    prompt_path = _PROMPTS_DIR / "agent2_system_prompt.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Agent 2 system prompt not found at: {prompt_path}. "
            "Ensure dischargeiq/prompts/agent2_system_prompt.txt exists."
        )
    return prompt_path.read_text(encoding="utf-8").strip()


def _build_user_message(extraction: ExtractionOutput) -> str:
    """
    Build the user message from Agent 1's ExtractionOutput.

    Passes primary diagnosis, secondary diagnoses, and procedures performed
    to give Claude enough context to explain what happened to the patient.

    Data contract: relies on ExtractionOutput fields from DIS-2 locked schema.
        - primary_diagnosis      (str, required)
        - secondary_diagnoses    (list[str], optional)
        - procedures_performed   (list[str], optional)

    Args:
        extraction: Validated ExtractionOutput from Agent 1.

    Returns:
        str: Formatted user message for the Claude API call.
    """
    lines = [f"Primary diagnosis: {extraction.primary_diagnosis}"]

    if extraction.secondary_diagnoses:
        lines.append(
            f"Secondary diagnoses: {', '.join(extraction.secondary_diagnoses)}"
        )

    if extraction.procedures_performed:
        lines.append(
            f"Procedures performed during hospital stay: "
            f"{', '.join(extraction.procedures_performed)}"
        )

    return "\n".join(lines)


def _log_fk_score(document_id: str, fk_result: dict) -> None:
    """
    Append an FK score result to dischargeiq/evaluation/fk_log.csv.

    Creates the file with a header row if it does not already exist.
    Per DIS-8 acceptance criteria — all Agent 2 FK scores must be logged.

    Args:
        document_id: Source document identifier (e.g. "heart_failure_01.pdf").
        fk_result:   Dict returned by fk_check() — keys: fk_grade, passes, threshold.
    """
    _FK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_header = not _FK_LOG_PATH.exists()

    with open(_FK_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["document_id", "agent", "fk_grade", "passes", "threshold"]
        )
        if write_header:
            writer.writeheader()
        writer.writerow({
            "document_id": document_id,
            "agent": "agent2_diagnosis",
            "fk_grade": fk_result["fk_grade"],
            "passes": fk_result["passes"],
            "threshold": fk_result["threshold"],
        })


# ── Public API ─────────────────────────────────────────────────────────────────

def run_diagnosis_agent(
    extraction: ExtractionOutput,
    document_id: str = "unknown",
) -> dict:
    """
    Agent 2: Generate a plain-language diagnosis explanation from Agent 1 output.

    Sends primary diagnosis (plus secondary diagnoses and procedures) to Claude
    with a patient-education system prompt. Scores the output with fk_check()
    and logs the result to dischargeiq/evaluation/fk_log.csv.

    Data contract:
        Input:  ExtractionOutput from Agent 1 (DIS-5).
                primary_diagnosis must not be None or empty.
        Output: dict with keys:
                    text     (str)   — plain-language explanation paragraph
                    fk_grade (float) — Flesch-Kincaid grade level of the output
                    passes   (bool)  — True if fk_grade <= 6.0

    Args:
        extraction:   Validated ExtractionOutput from Agent 1.
        document_id:  Source document label used in FK log and console output.

    Returns:
        dict with keys: text, fk_grade, passes.

    Raises:
        ValueError: If primary_diagnosis is missing from Agent 1 output.
        APIError:   If the Anthropic API call fails.
    """
    if not extraction.primary_diagnosis:
        raise ValueError(
            "Agent 2 requires primary_diagnosis from Agent 1 output. "
            f"Field is empty for document '{document_id}'."
        )

    system_prompt = _load_system_prompt()
    user_message = _build_user_message(extraction)

    try:
        response = _client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except APIError as e:
        logger.error("Agent 2 API call failed for '%s': %s", document_id, e)
        raise

    explanation = response.content[0].text.strip()

    # Score and log — required by DIS-8 acceptance criteria
    fk_result = fk_check(explanation)
    _log_fk_score(document_id, fk_result)

    if fk_result["passes"]:
        logger.info(
            "Agent 2 FK PASS '%s': grade %.2f", document_id, fk_result["fk_grade"]
        )
    else:
        logger.warning(
            "Agent 2 FK FAIL '%s': grade %.2f — revise agent2_system_prompt.txt",
            document_id, fk_result["fk_grade"],
        )

    return {
        "text": explanation,
        "fk_grade": fk_result["fk_grade"],
        "passes": fk_result["passes"],
    }

