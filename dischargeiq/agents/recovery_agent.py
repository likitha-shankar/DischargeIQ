"""
agents/recovery_agent.py

Agent 4 — Recovery Trajectory Agent (DIS-16).
Owner: Suchithra | Sprint 2 Week 3

Consumes ExtractionOutput.primary_diagnosis and procedures_performed from
Agent 1 and produces a plain-language week-by-week recovery guide.

Each week section covers: expected feelings, activity level, normal vs
alarming symptoms, and one specific goal. Output closes with a realistic
"When to expect improvement" section.

Every output is FK-scored via utils.scorer.fk_check() and logged to
dischargeiq/evaluation/fk_log.csv. Target: FK grade <= 6.0.

Wired into the pipeline in orchestrator.py alongside Agents 2 and 3.

Data contract:
    Input:  dischargeiq.models.extraction.ExtractionOutput (from Agent 1)
            Required: primary_diagnosis (str)
            Optional: procedures_performed (list[str])
    Output: dict with keys:
                text     (str)   — full week-by-week recovery guide
                fk_grade (float) — FK grade level of the output
                passes   (bool)  — True if fk_grade <= 6.0

Dependencies:
    - anthropic          (pip install anthropic)
    - ANTHROPIC_API_KEY  set in .env or environment
    - dischargeiq.models.extraction.ExtractionOutput
    - dischargeiq.utils.scorer.fk_check
    - dischargeiq/prompts/agent4_system_prompt.txt

BLOCKED BY: DIS-9 (Agents 1-3 confirmed end-to-end) must be done first.
"""

import csv
import logging
import os
from pathlib import Path

import anthropic

from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.utils.scorer import fk_check

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

_MODEL = "claude-sonnet-4-20250514"

# 1500 tokens so a 4-week guide + improvement section never gets truncated.
_MAX_TOKENS = 1500

# Paths resolved relative to this file so they work regardless of cwd.
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_FK_LOG_PATH = Path(__file__).parent.parent / "evaluation" / "fk_log.csv"

# Anthropic client initialised once at module load; reads ANTHROPIC_API_KEY from env.
_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_system_prompt() -> str:
    """
    Load the Agent 4 system prompt from dischargeiq/prompts/agent4_system_prompt.txt.

    Returns:
        str: The full system prompt text, whitespace-stripped.

    Raises:
        FileNotFoundError: If the prompt file does not exist at the expected path.
    """
    prompt_path = _PROMPTS_DIR / "agent4_system_prompt.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Agent 4 system prompt not found at: {prompt_path}. "
            "Ensure dischargeiq/prompts/agent4_system_prompt.txt exists."
        )
    return prompt_path.read_text(encoding="utf-8").strip()


def _build_user_message(extraction: ExtractionOutput) -> str:
    """
    Build the user message sent to the LLM from Agent 1's ExtractionOutput.

    Data contract:
        - primary_diagnosis     (str, required): The patient's main diagnosis.
        - procedures_performed  (list[str], optional): Procedures done during stay.
          Included when present so the LLM can tailor recovery milestones
          (e.g. hip replacement recovery differs from medical management alone).

    Args:
        extraction: Validated ExtractionOutput from Agent 1.

    Returns:
        str: Formatted user message ready for the LLM API call.
    """
    lines = [f"Primary diagnosis: {extraction.primary_diagnosis}"]

    if extraction.procedures_performed:
        lines.append(
            f"Procedures performed: {', '.join(extraction.procedures_performed)}"
        )

    if extraction.activity_restrictions:
        lines.append(
            f"Activity restrictions: {', '.join(extraction.activity_restrictions)}"
        )

    return "\n".join(lines)


def _log_fk_score(document_id: str, fk_result: dict) -> None:
    """
    Append an Agent 4 FK score result to dischargeiq/evaluation/fk_log.csv.

    Creates the file with a header row if it does not already exist.
    Per DIS-16 acceptance criteria — all Agent 4 FK scores must be logged.

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
                "agent": "agent4_recovery",
                "fk_grade": fk_result["fk_grade"],
                "passes": fk_result["passes"],
                "threshold": fk_result["threshold"],
            })
    except OSError as e:
        logger.warning("Could not write FK log for '%s': %s", document_id, e)


# ── Public API ─────────────────────────────────────────────────────────────────

def run_recovery_agent(
    extraction: ExtractionOutput,
    document_id: str = "unknown",
) -> dict:
    """
    Agent 4: Generate a week-by-week recovery guide from Agent 1 output.

    Produces a plain-language guide covering Weeks 1, 2, 3-4 and a
    "When to expect improvement" section. Each week covers: expected
    feelings, activity level, normal vs alarming symptoms, and one goal.

    Data contract:
        Input:  ExtractionOutput from Agent 1.
                primary_diagnosis must be a non-empty string.
                procedures_performed and activity_restrictions are optional.
        Output: dict with keys:
                    text     (str)   — full recovery timeline as plain text
                    fk_grade (float) — Flesch-Kincaid grade level
                    passes   (bool)  — True if fk_grade <= 6.0

    Args:
        extraction:  Validated ExtractionOutput from Agent 1.
        document_id: Source document label for FK logging and console output.

    Returns:
        dict with keys: text, fk_grade, passes.

    Raises:
        ValueError:          If primary_diagnosis is missing from Agent 1 output.
        anthropic.APIError:  If the Anthropic API call fails.
    """
    if not extraction.primary_diagnosis:
        raise ValueError(
            "Agent 4 requires primary_diagnosis from Agent 1 output. "
            f"Field is empty for document '{document_id}'."
        )

    system_prompt = _load_system_prompt()
    user_message = _build_user_message(extraction)

    logger.info("Agent 4 request — document: '%s'", document_id)

    try:
        response = _client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.APIError as e:
        logger.error("Agent 4 API call failed for '%s': %s", document_id, e)
        raise

    recovery_text = response.content[0].text.strip()

    # FK check — required by DIS-16 acceptance criteria.
    fk_result = fk_check(recovery_text)
    _log_fk_score(document_id, fk_result)

    if fk_result["passes"]:
        logger.info(
            "Agent 4 FK PASS '%s': grade %.2f", document_id, fk_result["fk_grade"]
        )
    else:
        logger.warning(
            "Agent 4 FK FAIL '%s': grade %.2f — revise agent4_system_prompt.txt",
            document_id,
            fk_result["fk_grade"],
        )

    return {
        "text": recovery_text,
        "fk_grade": fk_result["fk_grade"],
        "passes": fk_result["passes"],
    }
