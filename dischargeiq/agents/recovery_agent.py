"""
agents/recovery_agent.py

Agent 4 - Recovery Trajectory Agent.
Owner: Likitha Shankar

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
                text     (str)   - full week-by-week recovery guide
                fk_grade (float) - FK grade level of the output
                passes   (bool)  - True if fk_grade <= 6.0

Dependencies:
    - anthropic          (used on anthropic provider path only)
    - dischargeiq.utils.llm_client (load_agent_prompt, get_native_agent_client,
                                    call_chat_with_fallback, DEFAULT_ANTHROPIC_MODEL)
    - dischargeiq.utils.scorer (fk_check, log_fk_score)
    - dischargeiq.models.extraction.ExtractionOutput
    - dischargeiq/prompts/agent4_system_prompt.txt

BLOCKED BY: Agents 1–3 must be confirmed end-to-end first.
"""

import logging
import os

import anthropic

from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.utils.llm_client import (
    DEFAULT_ANTHROPIC_MODEL,
    call_chat_with_fallback,
    get_native_agent_client,
    load_agent_prompt,
)
from dischargeiq.utils.scorer import fk_check, log_fk_score

logger = logging.getLogger(__name__)

# 1600, not 1000: a week-by-week timeline at 6th-grade verbosity was hitting
# the old cap and truncating mid-sentence in the patient-facing UI.
_MAX_TOKENS = 1600


def _build_user_message(extraction: ExtractionOutput) -> str:
    """
    Build the user message sent to the LLM from Agent 1's ExtractionOutput.

    Passes every PDF-derived field relevant to recovery so the agent is
    grounded in the document rather than generic clinical knowledge.

    Data contract:
        - primary_diagnosis      (str, required)
        - secondary_diagnoses    (list[str], optional)
        - procedures_performed   (list[str], optional)
        - activity_restrictions  (list[str], optional)
        - dietary_restrictions   (list[str], optional)
        - red_flag_symptoms      (list[str], optional): Warn the patient when to call.
        - discharge_condition    (str, optional): Patient's state at discharge.

    Args:
        extraction: Validated ExtractionOutput from Agent 1 (scoped for Agent 4).

    Returns:
        str: Formatted user message ready for the LLM API call.
    """
    lines = [f"Primary diagnosis: {extraction.primary_diagnosis}"]

    if extraction.secondary_diagnoses:
        lines.append(
            f"Secondary diagnoses: {', '.join(extraction.secondary_diagnoses)}"
        )

    if extraction.procedures_performed:
        lines.append(
            f"Procedures performed: {', '.join(extraction.procedures_performed)}"
        )

    if extraction.discharge_condition:
        lines.append(f"Condition at discharge: {extraction.discharge_condition}")

    if extraction.activity_restrictions:
        lines.append(
            f"Activity restrictions: {', '.join(extraction.activity_restrictions)}"
        )

    if extraction.dietary_restrictions:
        lines.append(
            f"Dietary restrictions: {', '.join(extraction.dietary_restrictions)}"
        )

    if extraction.red_flag_symptoms:
        lines.append(
            f"Red flag symptoms from discharge summary: {', '.join(extraction.red_flag_symptoms)}"
        )

    return "\n".join(lines)


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
                    text     (str)   - full recovery timeline as plain text
                    fk_grade (float) - Flesch-Kincaid grade level
                    passes   (bool)  - True if fk_grade <= 6.0

    Args:
        extraction:  Validated ExtractionOutput from Agent 1.
        document_id: Source document label for FK logging and console output.

    Returns:
        dict with keys: text, fk_grade, passes.

    Raises:
        ValueError: If primary_diagnosis is missing from Agent 1 output.
        anthropic.APIError: If the Anthropic API call fails on the anthropic path.
        Exception: If the provider API call fails on non-anthropic paths.
    """
    if not extraction.primary_diagnosis:
        raise ValueError(
            "Agent 4 requires primary_diagnosis from Agent 1 output. "
            f"Field is empty for document '{document_id}'."
        )

    system_prompt = load_agent_prompt("agent4_system_prompt.txt")
    user_message = _build_user_message(extraction)

    logger.info("Agent 4 request - document: '%s'", document_id)

    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    client, model = get_native_agent_client(provider)

    if provider != "anthropic":
        try:
            recovery_text = call_chat_with_fallback(
                client=client,
                model_name=model,
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=_MAX_TOKENS,
                provider=provider,
                agent_name="Agent 4",
                document_id=document_id,
            )
        except Exception as e:
            logger.error("Agent 4 %s call failed for '%s': %s", provider, document_id, e)
            raise
    else:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as e:
            logger.error("Agent 4 Anthropic call failed for '%s': %s", document_id, e)
            raise
        # Guard: Anthropic occasionally returns an empty content array on
        # transient errors that don't raise.
        recovery_text = response.content[0].text.strip() if response.content else ""

    if recovery_text.strip():
        fk_result = fk_check(recovery_text)
        log_fk_score(document_id, "agent4_recovery", fk_result)
    else:
        fk_result = {"fk_grade": -1.0, "passes": False, "threshold": 6.0}

    if fk_result["passes"]:
        logger.info(
            "Agent 4 FK PASS '%s': grade %.2f", document_id, fk_result["fk_grade"]
        )
    else:
        logger.warning(
            "Agent 4 FK FAIL '%s': grade %.2f - revise agent4_system_prompt.txt",
            document_id,
            fk_result["fk_grade"],
        )

    return {
        "text": recovery_text,
        "fk_grade": fk_result["fk_grade"],
        "passes": fk_result["passes"],
    }
