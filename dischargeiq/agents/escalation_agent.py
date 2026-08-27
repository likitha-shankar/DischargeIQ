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
from dischargeiq.utils.audience import AUDIENCE_PATIENT, audience_instruction
from dischargeiq.utils.llm_client import (
    DEFAULT_ANTHROPIC_MODEL,
    anthropic_extra_body,
    call_chat_with_fallback,
    read_anthropic_completion,
    get_native_agent_client,
    load_agent_prompt,
)
from dischargeiq.utils.scorer import fk_check, log_fk_score

logger = logging.getLogger(__name__)

# Safety-critical output gets generous headroom: a real document with 15
# red flags plus per-symptom explanations exceeded 1000 and a truncated
# guide silently drops whole tiers (observed live July 2026).
_MAX_TOKENS = 2000

# Compiled once at import time; was rebuilt inside run_escalation_agent() on
# every call. agent5_system_prompt.txt forbids these phrases; we log a warning
# when the LLM emits one so operators can catch regression before eval day.
_AMBIGUOUS_PATTERN = re.compile(
    r"\bmay need to\b|\bmight need to\b|\bcould need\b"
    r"|\bconsider calling\b|\bconsider going\b|\byou may want to\b"
    r"|\bperhaps\b|\bif possible\b",
    re.IGNORECASE,
)


def _build_user_message(
    extraction: ExtractionOutput,
    audience: str = AUDIENCE_PATIENT,
) -> str:
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
        audience: Who the warning signs are written to, from
                  utils.audience.detect_audience(). The extraction schema has no
                  age field, so this arrives separately from the orchestrator.

    Returns:
        str: Formatted user message ready for the Claude API call.
    """
    lines = []

    # Audience first, so the model picks its addressee before any clinical text.
    instruction = audience_instruction(audience)
    if instruction:
        lines.append(instruction)

    lines.append(f"Primary diagnosis: {extraction.primary_diagnosis}")

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


# Explanation openings that carry no information. agent5_system_prompt.txt
# already forbids these, and on 25 Aug 2026 the model emitted "This is a
# medical emergency" six times in one guide anyway, pushing that document to
# FK 7.83 against a 6.0 target. The prompt rule stays; this is the check that
# makes it observable and recoverable.
_EMPTY_OPENERS = re.compile(
    r":\s*(this is|this can be|this means|you may feel|it is)\b",
    re.IGNORECASE,
)


def _degenerate_explanations(text: str) -> str | None:
    """
    Detect a guide whose bullet explanations have stopped saying anything.

    Two shapes, both seen in real output:

      REPETITION - the same explanation pasted after several symptoms
        ("- Sudden confusion: This is a medical emergency." x6). The guide
        looks full and tells the patient nothing about why any symptom
        matters, which is the entire job of the explanation half.
      EMPTY OPENERS - explanations starting "This is", "This means",
        "You may feel". The prompt forbids these by name because they spend
        words without naming a cause or a risk.

    Args:
        text: The full three-tier guide.

    Returns:
        A short reason string when the output is degenerate, else None. The
        reason is fed back to the model verbatim on retry, so it names the
        specific failure rather than asking generically for "better" output.
    """
    explanations = [
        part.split(":", 1)[1].strip().lower()
        for part in text.splitlines()
        if part.strip().startswith("-") and ":" in part
    ]
    explanations = [e for e in explanations if e]
    if len(explanations) >= 3:
        most_common = max(set(explanations), key=explanations.count)
        repeats = explanations.count(most_common)
        # Three identical explanations is not a coincidence; it is a model
        # that has stopped reading the symptom it is explaining.
        if repeats >= 3:
            return (
                f'the explanation "{most_common}" is repeated {repeats} times'
            )
    empty = len(_EMPTY_OPENERS.findall(text))
    if empty >= 3:
        return f"{empty} explanations begin with an empty phrase like 'This is'"
    return None


def run_escalation_agent(
    extraction: ExtractionOutput,
    document_id: str = "unknown",
    audience: str = AUDIENCE_PATIENT,
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
        audience:    AUDIENCE_PATIENT (default) or AUDIENCE_CAREGIVER, from
                     utils.audience.detect_audience() on the raw document.
                     Switches the text to address a parent for pediatric
                     patients. Defaults to the patient voice, so existing
                     callers are unaffected.

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
    user_message = _build_user_message(extraction, audience)

    logger.info(
        "Agent 5 request - document: '%s', red_flags: %d",
        document_id,
        len(extraction.red_flag_symptoms or []),
    )

    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    client, model = get_native_agent_client(provider)

    def _generate(message: str) -> str:
        """One generation attempt. Extracted so the retry reuses both paths."""
        if provider != "anthropic":
            try:
                return call_chat_with_fallback(
                    client=client,
                    model_name=model,
                    system_prompt=system_prompt,
                    user_message=message,
                    max_tokens=_MAX_TOKENS,
                    provider=provider,
                    agent_name="Agent 5",
                    document_id=document_id,
                )
            except Exception as e:
                logger.error("Agent 5 %s call failed for '%s': %s", provider, document_id, e)
                raise
        try:
            response = client.messages.create(
                model=model,
                max_tokens=_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": message}],
                # Claude 5 thinks by default and max_tokens covers thinking
                # plus the answer, which truncates bounded output. See
                # anthropic_extra_body in utils/llm_client.
                extra_body=anthropic_extra_body(model),
            )
        except anthropic.APIError as e:
            logger.error("Agent 5 Anthropic call failed for '%s': %s", document_id, e)
            raise
        # Empty-content and max_tokens truncation both fail loudly here -
        # see read_anthropic_completion.
        return read_anthropic_completion(response, "Agent 5", document_id)

    escalation_text = _generate(user_message)

    # One retry when the explanations have stopped saying anything. The prompt
    # already forbids empty openers, and on 25 Aug 2026 the model emitted
    # "This is a medical emergency" six times anyway, taking that document to
    # FK 7.83 against a 6.0 target. Agent 2 has had a retry for its own failure
    # mode since July; Agent 5 had none and simply logged "FK FAIL - revise the
    # prompt", which ships the bad guide.
    #
    # The retry names the specific defect rather than asking for better output,
    # and repeats the symptom-preservation rule, because the cheapest way to
    # satisfy "vary the explanations" would be to drop symptoms.
    degenerate = _degenerate_explanations(escalation_text)
    if degenerate:
        logger.warning(
            "Agent 5 retry '%s': %s - regenerating", document_id, degenerate,
        )
        retry_message = (
            user_message
            + f"\n\nYour previous guide was rejected because {degenerate}. "
            + "Every explanation after the colon must say something specific "
            + "about THAT symptom: name the cause or the risk. Never reuse the "
            + "same explanation twice, and never start one with 'This is', "
            + "'This means' or 'You may feel'. Keep every symptom you listed "
            + "before - fix the explanations, do not shorten the list."
        )
        retry_text = _generate(retry_message)
        # Never blindly prefer the retry: the same guard Agent 2 uses. The
        # retry is only accepted if it is no longer degenerate, still carries
        # the emergency tier, and did not lose symptoms. A shorter guide that
        # reads more easily is not an improvement in a safety-critical output.
        retry_bullets = sum(1 for line in retry_text.splitlines()
                            if line.strip().startswith("-"))
        first_bullets = sum(1 for line in escalation_text.splitlines()
                            if line.strip().startswith("-"))
        if (not _degenerate_explanations(retry_text)
                and "CALL 911" in retry_text.upper()
                and retry_bullets >= first_bullets):
            logger.info(
                "Agent 5 retry '%s' accepted: %d bullets kept",
                document_id, retry_bullets,
            )
            escalation_text = retry_text
        else:
            logger.warning(
                "Agent 5 retry '%s' REJECTED (degenerate=%s, bullets %d->%d) - "
                "keeping the first attempt",
                document_id, bool(_degenerate_explanations(retry_text)),
                first_bullets, retry_bullets,
            )

    # Structural safety gate: the three tier headers are the contract with
    # both UIs AND the patient's mental model. A guide missing the 911 tier
    # is dangerous - fail the agent (pipeline degrades to a labeled partial)
    # rather than ship it. Missing lower tiers log loudly but do not fail:
    # a guide with only the 911 tier is still safe, just incomplete.
    if escalation_text.strip() and "CALL 911" not in escalation_text.upper():
        raise ValueError(
            f"Agent 5 output for '{document_id}' is missing the CALL 911 tier - "
            "refusing to ship an escalation guide without the emergency tier."
        )
    for tier in ("GO TO THE ER", "CALL YOUR DOCTOR"):
        if tier not in escalation_text.upper():
            logger.warning(
                "Agent 5 output for '%s' is missing the '%s' tier header.",
                document_id, tier,
            )

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
