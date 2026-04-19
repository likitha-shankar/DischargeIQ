"""
agents/medication_agent.py

Agent 3 — Medication Rationale Agent (DIS-12).
Owner: Suchithra | Sprint 1 Week 2

Consumes ExtractionOutput.medications and ExtractionOutput.primary_diagnosis
from Agent 1 and produces a plain-language, per-medication explanation that
connects each drug to the patient's specific diagnosis.

Every output paragraph covers four points per medication:
  1. Why it was prescribed for this diagnosis
  2. What the patient will notice as it works
  3. Expected side effects (not a concern)
  4. Symptoms that require calling the doctor or going to the ER

Output is never medical advice. The agent must never tell a patient to
stop, reduce, or change a medication.

Every output is FK-scored via utils.scorer.fk_check() and logged to
dischargeiq/evaluation/fk_log.csv. Target: FK grade <= 6.0.

Data contract:
    Input:  dischargeiq.models.extraction.ExtractionOutput (from Agent 1)
            Required fields: primary_diagnosis, medications (list of Medication)
    Output: dict with keys:
                text     (str)   — full plain-language medication rationale
                fk_grade (float) — FK grade level of the combined output
                passes   (bool)  — True if fk_grade <= 6.0

Dependencies:
    - anthropic          (pip install anthropic)
    - ANTHROPIC_API_KEY  set in .env or environment
    - dischargeiq.models.extraction.ExtractionOutput, Medication
    - dischargeiq.utils.scorer.fk_check
    - dischargeiq/prompts/agent3_system_prompt.txt

BLOCKED BY: DIS-8 (Agent 2) must be confirmed before this is marked Done.
"""

import csv
import logging
import os
from pathlib import Path

from openai import OpenAI, APIError

from dischargeiq.models.extraction import ExtractionOutput, Medication
from dischargeiq.utils.scorer import fk_check

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

# Free model via OpenRouter for local dev.
# TODO: switch to Claude Sonnet before Sprint 2 eval run.
_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")

# 2000 tokens to handle up to ~10 medications at 3-5 sentences each.
_MAX_TOKENS = 2000

# Paths resolved relative to this file so they work regardless of cwd.
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_FK_LOG_PATH = Path(__file__).parent.parent / "evaluation" / "fk_log.csv"

# OpenRouter client initialised once at module load; reads OPENROUTER_API_KEY from env.
_client = OpenAI(
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
    base_url="https://openrouter.ai/api/v1",
)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_system_prompt() -> str:
    """
    Load the Agent 3 system prompt from dischargeiq/prompts/agent3_system_prompt.txt.

    Returns:
        str: The full system prompt text, whitespace-stripped.

    Raises:
        FileNotFoundError: If the prompt file does not exist at the expected path.
    """
    prompt_path = _PROMPTS_DIR / "agent3_system_prompt.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Agent 3 system prompt not found at: {prompt_path}. "
            "Ensure dischargeiq/prompts/agent3_system_prompt.txt exists."
        )
    return prompt_path.read_text(encoding="utf-8").strip()


def _format_medication_line(med: Medication) -> str:
    """
    Serialise a single Medication model into a compact text line for the LLM.

    Includes dose, frequency, and status when present. Missing optional
    fields are omitted rather than shown as 'None'.

    Args:
        med: A Medication instance from Agent 1's ExtractionOutput.

    Returns:
        str: A single-line summary, e.g. "Furosemide 40 mg, once daily (new)".
    """
    parts = [med.name]
    if med.dose:
        parts.append(med.dose)
    if med.frequency:
        parts.append(med.frequency)

    line = " ".join(parts)

    # Duration and status bracketed at the end for clarity.
    annotations = []
    if med.duration:
        annotations.append(f"for {med.duration}")
    if med.status:
        annotations.append(med.status)

    if annotations:
        line += f" ({', '.join(annotations)})"

    return line


def _build_user_message(extraction: ExtractionOutput) -> str:
    """
    Build the user message sent to Claude from Agent 1's ExtractionOutput.

    Data contract:
        - primary_diagnosis  (str, required): The patient's main diagnosis.
        - medications        (list[Medication]): Medications to explain.
          Each medication becomes one line in the prompt.
          Fields used: name (required), dose, frequency, duration, status (optional).

    If the medication list is empty this function still returns a valid message;
    the LLM will respond with a note that no medications were found.

    Args:
        extraction: Validated ExtractionOutput from Agent 1.

    Returns:
        str: Formatted user message ready for the Claude API call.
    """
    med_lines = [
        f"- {_format_medication_line(med)}"
        for med in extraction.medications
    ]

    if not med_lines:
        med_lines = ["- No medications listed in the discharge document."]

    medication_block = "\n".join(med_lines)

    return (
        f"Primary diagnosis: {extraction.primary_diagnosis}\n\n"
        f"Medications:\n{medication_block}"
    )


def _log_fk_score(document_id: str, fk_result: dict) -> None:
    """
    Append an Agent 3 FK score result to dischargeiq/evaluation/fk_log.csv.

    Creates the file with a header row if it does not already exist.
    Per DIS-12 acceptance criteria — all Agent 3 FK scores must be logged.

    Args:
        document_id: Source document identifier (e.g. "heart_failure_01.pdf").
        fk_result:   Dict returned by fk_check() — keys: fk_grade, passes, threshold.
    """
    _FK_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
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
                "agent": "agent3_medication",
                "fk_grade": fk_result["fk_grade"],
                "passes": fk_result["passes"],
                "threshold": fk_result["threshold"],
            })
    except OSError as e:
        # Log but do not crash — FK logging is non-critical
        logger.warning("Could not write FK log for '%s': %s", document_id, e)


# ── Public API ─────────────────────────────────────────────────────────────────

def run_medication_agent(
    extraction: ExtractionOutput,
    document_id: str = "unknown",
) -> dict:
    """
    Agent 3: Generate plain-language medication explanations from Agent 1 output.

    For each medication in extraction.medications, the LLM produces a short
    paragraph (3-5 sentences) covering: why it was prescribed, what the patient
    will notice, expected side effects, and when to call the doctor.

    Output is scored with fk_check() and logged to fk_log.csv. If the FK score
    exceeds 6.0, a warning is logged — the system prompt should be tightened.

    Data contract:
        Input:  ExtractionOutput from Agent 1.
                primary_diagnosis must be a non-empty string.
                medications is [] when no drugs were found (handled gracefully).
        Output: dict with keys:
                    text     (str)   — full per-medication explanation as plain text
                    fk_grade (float) — Flesch-Kincaid grade level of the combined output
                    passes   (bool)  — True if fk_grade <= 6.0

    Args:
        extraction:  Validated ExtractionOutput from Agent 1.
        document_id: Source document label for FK logging and console output.

    Returns:
        dict with keys: text, fk_grade, passes.

    Raises:
        ValueError: If primary_diagnosis is missing from Agent 1 output.
        APIError:   If the Anthropic API call fails after retries.
    """
    if not extraction.primary_diagnosis:
        raise ValueError(
            "Agent 3 requires primary_diagnosis from Agent 1 output. "
            f"Field is empty for document '{document_id}'."
        )

    system_prompt = _load_system_prompt()
    user_message = _build_user_message(extraction)

    logger.info(
        "Agent 3 request — document: '%s', medications: %d",
        document_id,
        len(extraction.medications),
    )

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
    except APIError as e:
        logger.error("Agent 3 API call failed for '%s': %s", document_id, e)
        raise

    rationale_text = response.choices[0].message.content.strip()

    # FK check on the combined output — required by DIS-12 acceptance criteria.
    fk_result = fk_check(rationale_text)
    _log_fk_score(document_id, fk_result)

    if fk_result["passes"]:
        logger.info(
            "Agent 3 FK PASS '%s': grade %.2f", document_id, fk_result["fk_grade"]
        )
    else:
        logger.warning(
            "Agent 3 FK FAIL '%s': grade %.2f — revise agent3_system_prompt.txt",
            document_id,
            fk_result["fk_grade"],
        )

    return {
        "text": rationale_text,
        "fk_grade": fk_result["fk_grade"],
        "passes": fk_result["passes"],
    }
