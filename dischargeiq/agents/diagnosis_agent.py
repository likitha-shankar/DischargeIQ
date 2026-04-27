"""
agents/diagnosis_agent.py

Agent 2 — Diagnosis Explanation Agent.
Owner: Deepesh Kumar

Consumes ExtractionOutput.primary_diagnosis (and secondary_diagnoses,
procedures_performed) from Agent 1 and produces a plain-language paragraph
explaining the diagnosis at a 6th grade Flesch-Kincaid reading level.

Every output is scored with utils.scorer.fk_check() before return.
FK scores are logged to dischargeiq/evaluation/fk_log.csv automatically.

LLM provider is resolved from LLM_PROVIDER / LLM_MODEL in .env via
dischargeiq.utils.llm_client.get_llm_client(). Changing LLM_PROVIDER
switches every agent in the pipeline (same as agents 3–5).

Data contract:
    Input:  dischargeiq.models.extraction.ExtractionOutput (from Agent 1)
    Output: dict with keys:
                text     (str)   — plain-language explanation paragraph
                fk_grade (float) — FK grade level of the output
                passes   (bool)  — True if fk_grade <= 6.0

Dependencies:
    - openai             (OpenAI-compatible client, used for all providers)
    - dischargeiq.utils.llm_client.get_llm_client
    - dischargeiq.models.extraction.ExtractionOutput
    - dischargeiq.utils.scorer.fk_check
    - dischargeiq/prompts/agent2_system_prompt.txt

BLOCKED BY: Agent 1 must be done before this runs in production.
"""

import csv
import logging
import os
from pathlib import Path

from openai import APIError, OpenAI

from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.utils.llm_client import call_chat_with_fallback, get_llm_client
from dischargeiq.utils.scorer import fk_check

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

_MAX_TOKENS = 500

# FK grade ceiling for accepting an explanation. 6.0 is
# ideal; 6.5 is the acceptable cap for complex multi-comorbidity cases where
# naming several conditions at once (e.g. AKI + CKD + diabetes + anemia)
# forces slightly longer clause structure. When the first attempt scores
# above this, Agent 2 issues exactly one simplification retry before
# accepting whichever of the two attempts scored lower.
_FK_RETRY_THRESHOLD = 6.5

# Paths resolved relative to this file
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_FK_LOG_PATH = Path(__file__).parent.parent / "evaluation" / "fk_log.csv"


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
    to give the LLM enough context to explain what happened to the patient.

    Data contract: relies on ExtractionOutput fields from the locked schema.
        - primary_diagnosis      (str, required)
        - secondary_diagnoses    (list[str], optional)
        - procedures_performed   (list[str], optional)

    Args:
        extraction: Validated ExtractionOutput from Agent 1.

    Returns:
        str: Formatted user message for the LLM API call.
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


def _call_llm(
    client: OpenAI,
    model_name: str,
    system_prompt: str,
    user_message: str,
    document_id: str,
) -> str:
    """
    Execute one chat completion against the configured LLM and return the text.

    Extracted so the retry path in run_diagnosis_agent() can invoke the same
    call pattern twice without duplicating the APIError handling and
    empty-response guard.

    Args:
        client:        OpenAI-compatible client from get_llm_client().
        model_name:    Model string resolved from LLM_MODEL env var.
        system_prompt: Agent 2 system prompt (patient-education instructions).
        user_message:  Either the base Agent-1-derived context or that context
                       plus a simplification reinforcement suffix on retry.
        document_id:   Source document label, used only for log context.

    Returns:
        str: Stripped explanation text from the LLM response.

    Raises:
        APIError:   If the LLM API call fails at transport level.
        ValueError: If the provider returns a response with no content
                    (e.g. content filter blocked the completion).
    """
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    try:
        return call_chat_with_fallback(
            client=client,
            model_name=model_name,
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=_MAX_TOKENS,
            provider=provider,
            agent_name="Agent 2",
            document_id=document_id,
        )
    except APIError as exc:
        logger.error("Agent 2 API call failed for '%s': %s", document_id, exc)
        raise


def _log_fk_score(document_id: str, fk_result: dict) -> None:
    """
    Append an FK score result to dischargeiq/evaluation/fk_log.csv.

    Creates the file with a header row if it does not already exist.
    All Agent 2 FK scores must be logged.

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

    Sends primary diagnosis (plus secondary diagnoses and procedures) to the
    configured LLM provider with a patient-education system prompt. Scores the
    output with fk_check() and logs the result to fk_log.csv.

    Provider and model are resolved from LLM_PROVIDER / LLM_MODEL in .env via
    get_llm_client(). Supports openrouter, openai, and ollama.

    Data contract:
        Input:  ExtractionOutput from Agent 1.
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
        ValueError:  If primary_diagnosis is missing from Agent 1 output, or if
                     the LLM returns an empty response.
        APIError:    If the LLM API call fails.
        ValueError:  If the required API key env var for the chosen provider is missing.
    """
    if not extraction.primary_diagnosis:
        raise ValueError(
            "Agent 2 requires primary_diagnosis from Agent 1 output. "
            f"Field is empty for document '{document_id}'."
        )

    system_prompt = _load_system_prompt()
    user_message = _build_user_message(extraction)

    # get_llm_client() reads LLM_PROVIDER and LLM_MODEL from the environment.
    # Changing .env switches the provider for all agents simultaneously.
    client, model_name = get_llm_client()

    # First attempt.
    explanation_1 = _call_llm(
        client, model_name, system_prompt, user_message, document_id,
    )
    fk_1 = fk_check(explanation_1)

    # Simplification retry gate. Target FK ≤ 6.0, but we allow up
    # to _FK_RETRY_THRESHOLD (6.5) without retrying because multi-comorbidity
    # cases (AKI + CKD + diabetes + anemia + HTN) force slightly longer clause
    # structure even at 6th-grade vocabulary. Anything above 6.5 gets exactly
    # one retry with an explicit simplification reinforcement appended to the
    # user message. We then accept whichever of the two attempts scored lower
    # — retries can occasionally regress, so we never blindly prefer attempt 2.
    if fk_1["fk_grade"] <= _FK_RETRY_THRESHOLD:
        chosen_text, chosen_fk = explanation_1, fk_1
        retried = False
    else:
        logger.warning(
            "Agent 2 retry '%s': first attempt FK=%.2f > %.1f — simplifying",
            document_id, fk_1["fk_grade"], _FK_RETRY_THRESHOLD,
        )
        # Reinforcement suffix is additive — the system prompt already carries
        # the full reading-level rules; this just pushes the model harder on
        # the specific failure mode (long compound sentences with
        # "which"/"because" subordinate clauses).
        retry_user_message = (
            user_message
            + "\n\nYour previous explanation scored "
            + f"{fk_1['fk_grade']:.1f} on Flesch-Kincaid. That is too hard to read. "
            + "Rewrite it at a 6th grade level. Maximum 15 words per sentence. "
            + "No subordinate clauses starting with 'which', 'that', 'because'. "
            + "Use 'also' not 'additionally', 'but' not 'however', 'so' not 'therefore'."
        )
        explanation_2 = _call_llm(
            client, model_name, system_prompt, retry_user_message, document_id,
        )
        fk_2 = fk_check(explanation_2)
        if fk_2["fk_grade"] < fk_1["fk_grade"]:
            chosen_text, chosen_fk = explanation_2, fk_2
        else:
            chosen_text, chosen_fk = explanation_1, fk_1
        retried = True
        logger.info(
            "Agent 2 retry result '%s': attempt1=%.2f attempt2=%.2f chose=%.2f",
            document_id, fk_1["fk_grade"], fk_2["fk_grade"], chosen_fk["fk_grade"],
        )

    # Only the accepted attempt is logged to fk_log.csv — downstream evaluators
    # see one row per document, not two rows for retried cases.
    _log_fk_score(document_id, chosen_fk)

    if chosen_fk["passes"]:
        logger.info(
            "Agent 2 FK PASS '%s': grade %.2f (retried=%s)",
            document_id, chosen_fk["fk_grade"], retried,
        )
    else:
        logger.warning(
            "Agent 2 FK FAIL '%s': grade %.2f (retried=%s) — revise agent2_system_prompt.txt",
            document_id, chosen_fk["fk_grade"], retried,
        )

    logger.info(
        "Agent 2 complete — '%s', FK grade: %.2f, passes: %s, length: %d chars",
        document_id,
        chosen_fk["fk_grade"],
        chosen_fk["passes"],
        len(chosen_text),
    )

    return {
        "text": chosen_text,
        "fk_grade": chosen_fk["fk_grade"],
        "passes": chosen_fk["passes"],
    }
