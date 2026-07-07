"""
agents/medication_agent.py

Agent 3 - Medication Rationale Agent.
Owner: Likitha Shankar

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
                text     (str)   - full plain-language medication rationale
                fk_grade (float) - FK grade level of the combined output
                passes   (bool)  - True if fk_grade <= 6.0

Dependencies:
    - anthropic          (used on anthropic provider path only)
    - dischargeiq.utils.llm_client (load_agent_prompt, get_native_agent_client,
                                    call_chat_with_fallback, DEFAULT_ANTHROPIC_MODEL)
    - dischargeiq.utils.scorer (fk_check, log_fk_score)
    - dischargeiq.models.extraction.ExtractionOutput, Medication
    - dischargeiq/prompts/agent3_system_prompt.txt

BLOCKED BY: Agent 2 must be confirmed before this is marked done.
"""

import logging
import os

import anthropic

from dischargeiq.models.extraction import ExtractionOutput, Medication
from dischargeiq.utils.llm_client import (
    DEFAULT_ANTHROPIC_MODEL,
    call_chat_with_fallback,
    get_native_agent_client,
    load_agent_prompt,
)
from dischargeiq.utils.scorer import fk_check, log_fk_score

logger = logging.getLogger(__name__)

_MAX_TOKENS = 1000


def _format_medication_line(med: Medication) -> str:
    """
    Serialise a single Medication model into a compact text block for the LLM.

    Includes dose, frequency, duration, and status when present. Missing
    optional fields are omitted rather than shown as 'None'. When the
    Medication carries a source span (the verbatim passage from the
    discharge PDF), it is appended on a second indented line as
    `Source: "..."`. Including the verbatim source lets Agent 3 detect
    critical safety language ("DO NOT STOP", stroke signs, 911 callouts)
    that the structured fields alone do not preserve.

    Args:
        med: A Medication instance from Agent 1's ExtractionOutput.

    Returns:
        str: Formatted block. The first line is the one-line summary, e.g.
             "Furosemide 40 mg, once daily (new)". When source text is
             present a second line follows with the verbatim passage.
    """
    parts = [med.name]
    if med.dose:
        parts.append(med.dose)
    if med.frequency:
        parts.append(med.frequency)

    line = " ".join(parts)

    annotations = []
    if med.duration:
        annotations.append(f"for {med.duration}")
    if med.status:
        annotations.append(med.status)

    if annotations:
        line += f" ({', '.join(annotations)})"

    # Append verbatim source text when Agent 1 captured a source span.
    # The LLM relies on this line to trigger the CRITICAL SAFETY LANGUAGE
    # rule in agent3_system_prompt.txt - do not abbreviate or rewrite it.
    if med.source and med.source.text:
        line += f'\n  Source: "{med.source.text}"'

    return line


def _build_user_message(
    extraction: ExtractionOutput,
    safety_context: str = "",
) -> str:
    """
    Build the user message sent to Claude from Agent 1's ExtractionOutput.

    Data contract:
        - primary_diagnosis  (str, required): The patient's main diagnosis.
        - medications        (list[Medication]): Medications to explain.
          Each medication becomes one line in the prompt.
          Fields used: name (required), dose, frequency, duration, status (optional).
        - safety_context     (str, optional): Cross-section safety language
          harvested from the full PDF by the orchestrator (e.g. stroke /
          911 callouts in a separate EMERGENCY block). Appended verbatim
          so the LLM can honour the CRITICAL SAFETY LANGUAGE rule in
          agent3_system_prompt.txt even when the warning does not live on
          the medication's own Source line.

    If the medication list is empty this function still returns a valid message;
    the LLM will respond with a note that no medications were found.

    Args:
        extraction:     Validated ExtractionOutput from Agent 1.
        safety_context: Optional cross-section safety block. Omitted when empty.

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

    message = (
        f"Primary diagnosis: {extraction.primary_diagnosis}\n\n"
        f"Medications:\n{medication_block}"
    )

    # Append the document-wide safety block last so it follows all the
    # per-drug lines - the LLM reads it in the context of the drug list
    # above, which is exactly the order the prompt's reasoning assumes.
    if safety_context:
        message += (
            "\n\nDOCUMENT SAFETY LANGUAGE - reproduce any critical warnings "
            "below verbatim in the relevant medication paragraphs:\n"
            f"{safety_context}"
        )

    return message


def run_medication_agent(
    extraction: ExtractionOutput,
    document_id: str = "unknown",
    safety_context: str = "",
) -> dict:
    """
    Agent 3: Generate plain-language medication explanations from Agent 1 output.

    For each medication in extraction.medications, the LLM produces a short
    paragraph (3-5 sentences) covering: why it was prescribed, what the patient
    will notice, expected side effects, and when to call the doctor.

    Output is scored with fk_check() and logged to fk_log.csv. If the FK score
    exceeds 6.0, a warning is logged - the system prompt should be tightened.

    Data contract:
        Input:  ExtractionOutput from Agent 1.
                primary_diagnosis must be a non-empty string.
                medications is [] when no drugs were found (handled gracefully).
        Output: dict with keys:
                    text     (str)   - full per-medication explanation as plain text
                    fk_grade (float) - Flesch-Kincaid grade level of the combined output
                    passes   (bool)  - True if fk_grade <= 6.0

    Args:
        extraction:     Validated ExtractionOutput from Agent 1.
        document_id:    Source document label for FK logging and console output.
        safety_context: Optional newline-joined safety sentences harvested by
                        the orchestrator from the full PDF text. Used to
                        surface cross-section warnings (e.g. a separate
                        EMERGENCY / 911 block) to the LLM so it can honour
                        the CRITICAL SAFETY LANGUAGE rule in
                        agent3_system_prompt.txt. Empty string disables the
                        extra block.

    Returns:
        dict with keys: text, fk_grade, passes.

    Raises:
        ValueError: If primary_diagnosis is missing from Agent 1 output.
        anthropic.APIError: If the Anthropic API call fails on the anthropic path.
        Exception: If the provider API call fails on non-anthropic paths.
    """
    if not extraction.primary_diagnosis:
        raise ValueError(
            "Agent 3 requires primary_diagnosis from Agent 1 output. "
            f"Field is empty for document '{document_id}'."
        )

    system_prompt = load_agent_prompt("agent3_system_prompt.txt")
    user_message = _build_user_message(extraction, safety_context=safety_context)

    logger.info(
        "Agent 3 request - document: '%s', medications: %d",
        document_id,
        len(extraction.medications),
    )

    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    client, model = get_native_agent_client(provider)

    if provider != "anthropic":
        try:
            rationale_text = call_chat_with_fallback(
                client=client,
                model_name=model,
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=_MAX_TOKENS,
                provider=provider,
                agent_name="Agent 3",
                document_id=document_id,
            )
        except Exception as e:
            logger.error("Agent 3 %s call failed for '%s': %s", provider, document_id, e)
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
            logger.error("Agent 3 Anthropic call failed for '%s': %s", document_id, e)
            raise
        # Guard: Anthropic occasionally returns an empty content array on
        # transient errors that don't raise.
        rationale_text = response.content[0].text.strip() if response.content else ""

    if rationale_text.strip():
        fk_result = fk_check(rationale_text)
        log_fk_score(document_id, "agent3_medication", fk_result)
    else:
        fk_result = {"fk_grade": -1.0, "passes": False, "threshold": 6.0}

    if fk_result["passes"]:
        logger.info(
            "Agent 3 FK PASS '%s': grade %.2f", document_id, fk_result["fk_grade"]
        )
    else:
        logger.warning(
            "Agent 3 FK FAIL '%s': grade %.2f - revise agent3_system_prompt.txt",
            document_id,
            fk_result["fk_grade"],
        )

    return {
        "text": rationale_text,
        "fk_grade": fk_result["fk_grade"],
        "passes": fk_result["passes"],
    }
