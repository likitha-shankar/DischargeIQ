"""
agents/escalation_agent.py

Agent 5 - Escalation / Warning-Sign Agent. Safety-critical.
Owner: Likitha

Consumes Agent 1's ExtractionOutput and produces a three-tier decision
tree that tells the patient when to call 911, when to go to the ER
today, and when to call their doctor during office hours.

Tier ordering, headers, and subtitles are fixed by agent5_system_prompt.txt
and are parsed downstream by streamlit_app.py. Do not change the tier
header strings without updating the UI renderer at the same time.

Every output is FK-scored via utils.scorer.fk_check() and logged to
dischargeiq/evaluation/fk_log.csv. Target: FK grade <= 6.0.

LLM provider is resolved from LLM_PROVIDER / LLM_MODEL in .env via
get_native_agent_client(): native Anthropic client or OpenAI-compatible
clients for gemini / openrouter / openai / ollama.

Data contract:
    Input:  dischargeiq.models.extraction.ExtractionOutput (from Agent 1)
            Required: primary_diagnosis (str)
            Required: red_flag_symptoms (list[str]) - every entry must
                      land in exactly one tier.
            Optional: secondary_diagnoses (list[str])
            Optional: medications (list[Medication]) - used as context so
                      the LLM can factor medication side-effects into
                      tier assignment (e.g. warfarin → Tier 1 bleeding).
    Output: dict with keys:
                text     (str)   - full three-tier escalation guide
                fk_grade (float) - FK grade level of the output
                passes   (bool)  - True if fk_grade <= 6.0

Dependencies:
    - anthropic          (used on anthropic provider path only)
    - dischargeiq.utils.llm_client (load_agent_prompt, get_native_agent_client,
                                    call_chat_with_fallback, DEFAULT_ANTHROPIC_MODEL)
    - dischargeiq.utils.scorer (fk_check, log_fk_score)
    - dischargeiq.models.extraction.ExtractionOutput
    - dischargeiq/prompts/agent5_system_prompt.txt

BLOCKED BY: Agent 4 must be landed before Agent 5 is wired into the orchestrator.
"""

import logging
import os
import re

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

_MAX_TOKENS = 1000

# Compiled once at import time; was rebuilt inside run_escalation_agent() on
# every call. agent5_system_prompt.txt forbids these phrases; we log a warning
# when the LLM emits one so operators can catch regression before eval day.
_AMBIGUOUS_PATTERN = re.compile(
    r"\bmay need to\b|\bmight need to\b|\bcould need\b"
    r"|\bconsider calling\b|\bconsider going\b|\byou may want to\b"
    r"|\bperhaps\b|\bif possible\b",
    re.IGNORECASE,
)


def _build_user_message(extraction: ExtractionOutput) -> str:
    """
    Build the user message sent to Claude from Agent 1's ExtractionOutput.

    Structure:
        Primary diagnosis: <str>
        Secondary diagnoses: <comma-joined, or "none">
        Red-flag symptoms:
          1. <symptom>
          2. <symptom>
          ...
        Medications:
          - <name> <dose>
          ...

    Medications are included name + dose only - never dosing schedules
    or statuses - so the LLM can factor drug-specific risk (e.g. warfarin
    bleeding, metoprolol bradycardia) into tier placement without being
    tempted to comment on adherence.

    Args:
        extraction: Validated ExtractionOutput from Agent 1.

    Returns:
        str: Formatted user message ready for the Claude API call.
    """
    lines = [f"Primary diagnosis: {extraction.primary_diagnosis}"]

    secondary = extraction.secondary_diagnoses or []
    lines.append(
        "Secondary diagnoses: "
        + (", ".join(secondary) if secondary else "none")
    )

    red_flags = extraction.red_flag_symptoms or []
    if red_flags:
        lines.append("")
        lines.append("Red-flag symptoms:")
        for idx, symptom in enumerate(red_flags, start=1):
            lines.append(f"  {idx}. {symptom}")
    else:
        # Explicitly signal empty to the LLM so it still emits universally
        # life-threatening Tier 1 entries (cannot breathe, stroke signs, etc.)
        # rather than returning an empty tier block.
        lines.append("")
        lines.append(
            "Red-flag symptoms: none listed in discharge document."
        )

    meds = extraction.medications or []
    if meds:
        lines.append("")
        lines.append("Medications:")
        for med in meds:
            dose = f" {med.dose}" if med.dose else ""
            lines.append(f"  - {med.name}{dose}")

    return "\n".join(lines)


def run_escalation_agent(
    extraction: ExtractionOutput,
    document_id: str = "unknown",
) -> dict:
    """
    Agent 5: Generate the three-tier escalation decision tree.

    Sends Agent 1's extraction data to the configured LLM with the Agent 5
    safety prompt, then scores the output with fk_check() and logs the score.
    Output structure is fixed by agent5_system_prompt.txt and parsed by
    the Streamlit renderer - never change tier header strings without
    updating the UI.

    Provider and model are resolved from LLM_PROVIDER / LLM_MODEL in .env via
    get_native_agent_client() (Anthropic native or OpenAI-compatible for
    gemini, openrouter, openai, ollama).

    Data contract:
        Input:  ExtractionOutput from Agent 1.
                primary_diagnosis must be a non-empty string.
                red_flag_symptoms is [] when none were extracted - in that
                case the LLM still emits universally life-threatening
                Tier 1 entries (cannot breathe, stroke signs, etc.).
        Output: dict with keys:
                    text     (str)   - full three-tier guide as plain text
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
            "Agent 5 requires primary_diagnosis from Agent 1 output. "
            f"Field is empty for document '{document_id}'."
        )

    system_prompt = load_agent_prompt("agent5_system_prompt.txt")
    user_message = _build_user_message(extraction)

    logger.info(
        "Agent 5 request - document: '%s', red_flags: %d",
        document_id,
        len(extraction.red_flag_symptoms or []),
    )

    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    client, model = get_native_agent_client(provider)

    if provider != "anthropic":
        try:
            escalation_text = call_chat_with_fallback(
                client=client,
                model_name=model,
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=_MAX_TOKENS,
                provider=provider,
                agent_name="Agent 5",
                document_id=document_id,
            )
        except Exception as e:
            logger.error("Agent 5 %s call failed for '%s': %s", provider, document_id, e)
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
            logger.error("Agent 5 Anthropic call failed for '%s': %s", document_id, e)
            raise
        # Guard: Anthropic occasionally returns an empty content array on
        # transient errors that don't raise.
        escalation_text = response.content[0].text.strip() if response.content else ""

    # Runtime ambiguity check - agent5_system_prompt.txt forbids these phrases,
    # but we log a warning if the LLM slips one through so operators can catch it.
    if _AMBIGUOUS_PATTERN.search(escalation_text):
        logger.warning(
            "Agent 5 AMBIGUITY '%s': output contains a forbidden hedging phrase. "
            "Review agent5_system_prompt.txt.",
            document_id,
        )

    if escalation_text.strip():
        fk_result = fk_check(escalation_text)
        log_fk_score(document_id, "agent5_escalation", fk_result)
    else:
        fk_result = {"fk_grade": -1.0, "passes": False, "threshold": 6.0}

    if fk_result["passes"]:
        logger.info(
            "Agent 5 FK PASS '%s': grade %.2f",
            document_id,
            fk_result["fk_grade"],
        )
    else:
        logger.warning(
            "Agent 5 FK FAIL '%s': grade %.2f - revise agent5_system_prompt.txt",
            document_id,
            fk_result["fk_grade"],
        )

    return {
        "text": escalation_text,
        "fk_grade": fk_result["fk_grade"],
        "passes": fk_result["passes"],
    }
