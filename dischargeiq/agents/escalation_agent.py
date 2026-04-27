"""
agents/escalation_agent.py

Agent 5 — Escalation / Warning-Sign Agent. Safety-critical.
Owner: Likitha

Consumes Agent 1's ExtractionOutput and produces a three-tier decision
tree that tells the patient when to call 911, when to go to the ER
today, and when to call their doctor during office hours.

Tier ordering, headers, and subtitles are fixed by agent5_system_prompt.txt
and are parsed downstream by streamlit_app.py. Do not change the tier
header strings without updating the UI renderer at the same time.

Every output is FK-scored via utils.scorer.fk_check() and logged to
dischargeiq/evaluation/fk_log.csv. Target: FK grade <= 6.0.

LLM provider is resolved from LLM_PROVIDER / LLM_MODEL in .env via the same
multi-provider pattern as agents 3–4: native Anthropic client or OpenAI-
compatible clients for openrouter / openai / ollama (see _get_client()).

Data contract:
    Input:  dischargeiq.models.extraction.ExtractionOutput (from Agent 1)
            Required: primary_diagnosis (str)
            Required: red_flag_symptoms (list[str]) — every entry must
                      land in exactly one tier.
            Optional: secondary_diagnoses (list[str])
            Optional: medications (list[Medication]) — used as context so
                      the LLM can factor medication side-effects into
                      tier assignment (e.g. warfarin → Tier 1 bleeding).
    Output: dict with keys:
                text     (str)   — full three-tier escalation guide
                fk_grade (float) — FK grade level of the output
                passes   (bool)  — True if fk_grade <= 6.0

Dependencies:
    - anthropic, openai  (provider-specific clients per LLM_PROVIDER)
    - dischargeiq.utils.llm_client (call_chat_with_fallback,
      require_provider_api_key, DEFAULT_ANTHROPIC_MODEL)
    - dischargeiq.models.extraction.ExtractionOutput
    - dischargeiq.utils.scorer.fk_check
    - dischargeiq/prompts/agent5_system_prompt.txt

BLOCKED BY: Agent 4 must be landed before Agent 5 is wired
into the orchestrator.
"""

import csv
import logging
import os
from pathlib import Path
from typing import Any

import anthropic
from openai import OpenAI

from dischargeiq.models.extraction import ExtractionOutput
from dischargeiq.utils.llm_client import (
    DEFAULT_ANTHROPIC_MODEL,
    call_chat_with_fallback,
    require_provider_api_key,
)
from dischargeiq.utils.scorer import fk_check

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

_MODEL = DEFAULT_ANTHROPIC_MODEL

# 1000 tokens is ample for a structured three-tier guide. The output is
# deliberately short — 3 tier headers + ~3-6 bullets per tier × 1-2 short
# sentences per bullet. Raising this cap would only serve runaway output.
_MAX_TOKENS = 1000

# Paths resolved relative to this file so they work regardless of cwd.
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_FK_LOG_PATH = Path(__file__).parent.parent / "evaluation" / "fk_log.csv"


# ── Internal helpers ───────────────────────────────────────────────────────────


def _get_client() -> Any:
    """
    Return an LLM client based on the LLM_PROVIDER environment setting.

    Supported providers:
        - anthropic  -> anthropic.Anthropic (default)
        - openrouter -> openai.OpenAI with OpenRouter base_url
        - openai     -> openai.OpenAI with api.openai.com base_url
        - ollama     -> openai.OpenAI with local Ollama base_url

    Constructing the client at module import time would capture an empty
    ANTHROPIC_API_KEY when this module is imported before .env is loaded
    (e.g. via `from dischargeiq.pipeline.orchestrator import run_pipeline`
    at the top of main.py, which executes before main.py's load_dotenv).

    Returns:
        Any: Configured client instance for the selected provider.

    Raises:
        ValueError: If provider-specific API credentials are missing.

    Note:
        Timeout is provider-aware: 180s on OpenRouter/Ollama and 60s on
        Anthropic/OpenAI.
    """
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    require_provider_api_key(provider)
    timeout = 180.0 if provider in {"openrouter", "ollama"} else 60.0
    if provider == "openrouter":
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"].strip(),
            timeout=timeout,
            max_retries=1,
        )
    if provider == "openai":
        return OpenAI(
            base_url="https://api.openai.com/v1",
            api_key=os.environ["OPENAI_API_KEY"].strip(),
            timeout=timeout,
            max_retries=1,
        )
    if provider == "ollama":
        return OpenAI(
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key="ollama",
            timeout=timeout,
            max_retries=1,
        )
    return anthropic.Anthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"].strip(),
        timeout=timeout,
        max_retries=1,
    )


def _load_system_prompt() -> str:
    """
    Load the Agent 5 system prompt from dischargeiq/prompts/agent5_system_prompt.txt.

    Returns:
        str: The full system prompt text, whitespace-stripped.

    Raises:
        FileNotFoundError: If the prompt file does not exist at the expected path.
    """
    prompt_path = _PROMPTS_DIR / "agent5_system_prompt.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Agent 5 system prompt not found at: {prompt_path}. "
            "Ensure dischargeiq/prompts/agent5_system_prompt.txt exists."
        )
    return prompt_path.read_text(encoding="utf-8").strip()


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

    Medications are included name + dose only — never dosing schedules
    or statuses — so the LLM can factor drug-specific risk (e.g. warfarin
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


def _log_fk_score(document_id: str, fk_result: dict) -> None:
    """
    Append an Agent 5 FK score result to dischargeiq/evaluation/fk_log.csv.

    Creates the file with a header row if it does not already exist.
    All Agent 5 FK scores must be logged.

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
                "agent": "agent5_escalation",
                "fk_grade": fk_result["fk_grade"],
                "passes": fk_result["passes"],
                "threshold": fk_result["threshold"],
            })
    except OSError as e:
        # FK logging is non-critical — a disk error must never break the
        # pipeline's primary job of returning the escalation guide to the
        # patient.
        logger.warning("Could not write FK log for '%s': %s", document_id, e)


# ── Public API ─────────────────────────────────────────────────────────────────


def run_escalation_agent(
    extraction: ExtractionOutput,
    document_id: str = "unknown",
) -> dict:
    """
    Agent 5: Generate the three-tier escalation decision tree.

    Sends Agent 1's extraction data to the configured LLM with the Agent 5
    safety prompt, then scores the output with fk_check() and logs the score.
    Output structure is fixed by agent5_system_prompt.txt and parsed by
    the Streamlit renderer — never change tier header strings without
    updating the UI.

    Provider and model are resolved from LLM_PROVIDER / LLM_MODEL in .env via
    _get_client() (Anthropic native or OpenAI-compatible for openrouter, openai,
    ollama).

    Data contract:
        Input:  ExtractionOutput from Agent 1.
                primary_diagnosis must be a non-empty string.
                red_flag_symptoms is [] when none were extracted — in that
                case the LLM still emits universally life-threatening
                Tier 1 entries (cannot breathe, stroke signs, etc.).
        Output: dict with keys:
                    text     (str)   — full three-tier guide as plain text
                    fk_grade (float) — Flesch-Kincaid grade level
                    passes   (bool)  — True if fk_grade <= 6.0

    Args:
        extraction:  Validated ExtractionOutput from Agent 1.
        document_id: Source document label for FK logging and console output.

    Returns:
        dict with keys: text, fk_grade, passes.

    Raises:
        ValueError: If primary_diagnosis is missing from Agent 1 output.
        anthropic.APIError: If the Anthropic API call fails on the Anthropic path.
        Exception: If the OpenRouter API call fails.
    """
    if not extraction.primary_diagnosis:
        raise ValueError(
            "Agent 5 requires primary_diagnosis from Agent 1 output. "
            f"Field is empty for document '{document_id}'."
        )

    system_prompt = _load_system_prompt()
    user_message = _build_user_message(extraction)

    logger.info(
        "Agent 5 request — document: '%s', red_flags: %d",
        document_id,
        len(extraction.red_flag_symptoms or []),
    )

    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    client = _get_client()

    if provider != "anthropic":
        default_model = {
            "openrouter": "openrouter/free",
            "openai": "gpt-4o-mini",
            "ollama": "qwen2.5:7b",
        }.get(provider, "openrouter/free")
        model = os.environ.get("LLM_MODEL", default_model)
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
            logger.error("Agent 5 OpenRouter call failed for '%s': %s", document_id, e)
            raise
    else:
        model = os.environ.get("LLM_MODEL", DEFAULT_ANTHROPIC_MODEL)
        try:
            response = client.messages.create(
                model=model,
                max_tokens=_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
        except anthropic.APIError as e:
            logger.error("Agent 5 API call failed for '%s': %s", document_id, e)
            raise
        escalation_text = response.content[0].text.strip()

    # FK check. Safety output must
    # be legible at a 6th-grade reading level; a failing score means the
    # prompt needs tightening, not a silent retry.
    fk_result = fk_check(escalation_text)
    _log_fk_score(document_id, fk_result)

    if fk_result["passes"]:
        logger.info(
            "Agent 5 FK PASS '%s': grade %.2f",
            document_id,
            fk_result["fk_grade"],
        )
    else:
        logger.warning(
            "Agent 5 FK FAIL '%s': grade %.2f — revise agent5_system_prompt.txt",
            document_id,
            fk_result["fk_grade"],
        )

    return {
        "text": escalation_text,
        "fk_grade": fk_result["fk_grade"],
        "passes": fk_result["passes"],
    }
