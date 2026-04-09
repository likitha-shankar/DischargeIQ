"""
Agent 1 — Extraction agent (DIS-5).

Reads discharge document text (extracted via pdfplumber) and calls the LLM
with agent1_system_prompt.txt to produce JSON matching ExtractionOutput.
Validates the response with Pydantic; never fabricates field values —
missing data is returned as null or [] per the locked schema contract.

Depends on: google-generativeai, pdfplumber, pydantic v2,
            dischargeiq.models.extraction, prompts/agent1_system_prompt.txt.
"""

import json
import logging
import os
import time
from pathlib import Path

import google.generativeai as genai
import pdfplumber
from pydantic import ValidationError

from dischargeiq.models.extraction import ExtractionOutput

logger = logging.getLogger(__name__)

# Absolute path to the prompts directory, resolved relative to this file.
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# JSON schema description injected into every user message so the model
# knows the exact field names, types, and null-vs-empty rules.
_SCHEMA_BLOCK = """
Return a single JSON object with these fields (no extra keys, no commentary):

{
  "patient_name":             string or null,
  "discharge_date":           string or null  (e.g. "2024-03-15"),
  "primary_diagnosis":        string          (REQUIRED — never null),
  "secondary_diagnoses":      array of strings ([] if none),
  "procedures_performed":     array of strings ([] if none),
  "medications": [
    {
      "name":      string (REQUIRED),
      "dose":      string or null,
      "frequency": string or null,
      "duration":  string or null,
      "status":    "new" | "changed" | "continued" | "discontinued" | null
    }
  ],
  "follow_up_appointments": [
    {
      "provider":  string or null,
      "specialty": string or null,
      "date":      string or null,
      "reason":    string or null
    }
  ],
  "activity_restrictions":  array of strings ([] if none),
  "dietary_restrictions":   array of strings ([] if none),
  "red_flag_symptoms":      array of strings ([] if none),
  "discharge_condition":    string or null,
  "extraction_warnings":    array of strings ([] if none)
}
"""


def _load_system_prompt() -> str:
    """
    Load the Agent 1 system prompt from disk.

    Returns:
        str: Contents of agent1_system_prompt.txt, stripped of trailing whitespace.

    Raises:
        FileNotFoundError: If the prompt file does not exist at the expected path.
        OSError: If the file cannot be read due to a permissions or I/O error.
    """
    prompt_path = _PROMPTS_DIR / "agent1_system_prompt.txt"
    try:
        return prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.error("agent1_system_prompt.txt not found at %s", prompt_path)
        raise
    except OSError as exc:
        logger.error("Failed to read system prompt: %s", exc)
        raise


def _build_user_message(pdf_text: str) -> str:
    """
    Construct the user-turn message sent to the LLM.

    Combines the schema description with the raw discharge document text so
    the model has both the output contract and the source material in a
    single message.

    Args:
        pdf_text: Raw text extracted from the discharge PDF via pdfplumber.

    Returns:
        str: Formatted prompt string ready to pass to generate_content().
    """
    return (
        f"Extract all structured fields from the hospital discharge document below.\n\n"
        f"REQUIRED OUTPUT FORMAT:{_SCHEMA_BLOCK}\n"
        f"DISCHARGE DOCUMENT:\n{pdf_text}"
    )


def _is_per_minute_quota_error(exc: Exception) -> bool:
    """
    Return True only for per-minute quota errors that resolve within ~60s.

    Distinguishes per-minute rate limits (retryable after one minute) from
    daily quota exhaustion (not retryable until UTC midnight). Gemini raises
    both as ResourceExhausted (HTTP 429); the quota_id string in the body
    tells them apart. We inspect str(exc) to stay decoupled from gRPC internals.

    Per-minute: quota_id contains "PerMinute"  → retry after 65s
    Daily:      quota_id contains "PerDay"      → fail fast, wait until tomorrow

    Args:
        exc: The caught exception.

    Returns:
        bool: True if this is a per-minute limit worth retrying.
    """
    error_text = str(exc)
    is_quota = "quota" in error_text.lower() or "429" in error_text or "ResourceExhausted" in error_text
    is_daily = "PerDay" in error_text or "per_day" in error_text.lower()
    return is_quota and not is_daily


def _call_gemini(system_prompt: str, pdf_text: str) -> str:
    """
    Send the extraction request to Gemini and return the raw text response.

    Configures the API key from the environment, initialises the model with
    the system instruction, and sends the user message.

    Retries once on per-minute quota errors (HTTP 429) after waiting
    _QUOTA_RETRY_WAIT_SECONDS. Does not retry on daily quota exhaustion —
    the caller will receive the exception in that case.

    Set GEMINI_MODEL in the environment to override the model name
    (default: gemini-2.0-flash). Use gemini-1.5-flash if the daily
    quota for gemini-2.0-flash is exhausted on the free tier.

    Args:
        system_prompt: System instruction string loaded from the prompt file.
        pdf_text: Raw discharge document text to be extracted.

    Returns:
        str: Raw text response from Gemini, stripped of leading/trailing whitespace.

    Raises:
        Exception: Re-raises any API error (including quota errors after retries)
                   after logging.
    """
    # TODO DIS-5: Using Google Gemini (gemini-2.0-flash) for local
    # development due to API credit constraints. Switch to
    # claude-sonnet-4-20250514 via Anthropic SDK before Sprint 2
    # Week 5 evaluation run. See CLAUDE.md for the correct pattern.
    genai.configure(api_key=os.environ["GOOGLE_STUDIO_API_KEY"])

    # Allow model override via env var so the team can switch to
    # gemini-1.5-flash without code changes if 2.0-flash quota is exhausted.
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
    user_message = _build_user_message(pdf_text)

    # Single retry on per-minute quota reset (free tier = 15 RPM).
    # 65 seconds gives the one-minute window time to fully clear.
    _quota_retry_wait_seconds = 65
    _max_retries = 1

    for attempt in range(_max_retries + 1):
        try:
            response = model.generate_content(user_message)
            return response.text.strip()
        except Exception as exc:
            # Only retry per-minute limits — daily quota cannot be resolved by
            # waiting 65 seconds, so fail immediately with a clear message.
            if _is_per_minute_quota_error(exc) and attempt < _max_retries:
                logger.warning(
                    "Per-minute quota hit (attempt %d) — waiting %ds before retry.",
                    attempt + 1,
                    _quota_retry_wait_seconds,
                )
                time.sleep(_quota_retry_wait_seconds)
            else:
                logger.error("Gemini API call failed: %s", exc)
                raise


def _strip_markdown_fences(raw: str) -> str:
    """
    Remove markdown code fences that LLMs sometimes wrap around JSON.

    Args:
        raw: Raw LLM response that may contain ```json ... ``` wrappers.

    Returns:
        str: Cleaned string with fences removed, ready for json.loads().
    """
    # Strip the fenced code block markers the LLM sometimes adds despite
    # the prompt instructing it not to.
    return raw.replace("```json", "").replace("```", "").strip()


def _remove_stray_tokens(text: str) -> str:
    """
    Filter out lines that cannot be part of valid JSON syntax.

    Each line is accepted only if its first non-whitespace character is a
    recognised JSON structural character or the start of a JSON keyword.
    Lines that fail this check are dropped silently.

    Accepted first characters:
        { } [ ]   — object/array boundaries
        "         — string key or value
        , :       — separators (sometimes appear on their own line)
        0-9  -    — numeric literals
        t         — true
        f         — false
        n         — null

    Args:
        text: JSON text that may contain stray non-JSON lines.

    Returns:
        str: Text with non-JSON lines removed, preserving original line order.
    """
    _valid_json_starts = frozenset('{}[]",-:')

    filtered_lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if not stripped:
            # Blank / whitespace-only line — harmless, keep it.
            filtered_lines.append(line)
            continue

        first_char = stripped[0]
        is_structural = first_char in _valid_json_starts
        is_numeric = first_char.isdigit() or first_char == "-"
        is_keyword = stripped.startswith(("true", "false", "null"))

        if is_structural or is_numeric or is_keyword:
            filtered_lines.append(line)
        # Any other start character is a stray token — drop the line.

    return "\n".join(filtered_lines)


def _parse_and_validate(raw_response: str) -> ExtractionOutput:
    """
    Parse the LLM's raw text response into a validated ExtractionOutput model.

    Attempts a clean parse first. If json.loads() fails, applies
    _remove_stray_tokens() to strip non-JSON lines injected by the LLM and
    retries once. The original JSONDecodeError is re-raised if both attempts
    fail, with the cleaned text logged for debugging.

    Args:
        raw_response: Raw text from the LLM, possibly wrapped in markdown fences
                      and/or containing stray non-JSON tokens.

    Returns:
        ExtractionOutput: Validated Pydantic model with all extracted fields.

    Raises:
        json.JSONDecodeError: If the response cannot be parsed as JSON even after
                              stray-token removal.
        pydantic.ValidationError: If the JSON does not match the ExtractionOutput
                                   schema (e.g. primary_diagnosis is missing).
    """
    cleaned = _strip_markdown_fences(raw_response)

    # --- First attempt: clean parse (fast path, no mutation) ---
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as first_exc:
        # Gemini occasionally inserts stray tokens mid-JSON on
        # table-heavy documents. This cleanup step removes non-JSON
        # lines before parsing. Remove when switching to Claude API.
        logger.warning(
            "Initial JSON parse failed (%s). Attempting stray-token cleanup.",
            first_exc.msg,
        )
        sanitised = _remove_stray_tokens(cleaned)
        try:
            data = json.loads(sanitised)
            logger.info("JSON parse succeeded after stray-token cleanup.")
        except json.JSONDecodeError:
            # Both attempts failed — log the sanitised text and raise the
            # original error so the caller sees the first failure point.
            logger.error(
                "JSON parse failed after cleanup. Sanitised response:\n%s\n"
                "Original error: %s",
                sanitised,
                first_exc,
            )
            raise first_exc

    try:
        return ExtractionOutput(**data)
    except ValidationError as exc:
        logger.error("Pydantic validation failed: %s", exc)
        raise


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all text from a PDF file using pdfplumber.

    Pages are joined with double newlines to preserve visual separation between
    sections, which helps the LLM distinguish medication lists, instructions, etc.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        str: Concatenated text from all pages. Empty string if the PDF has
             no extractable text.

    Raises:
        FileNotFoundError: If the file does not exist at pdf_path.
        pdfplumber.exceptions.PDFSyntaxError: If the file is not a valid PDF.
        OSError: If the file cannot be opened due to permissions or I/O errors.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Join pages with double newline so section boundaries are preserved.
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(pages).strip()
    except FileNotFoundError:
        logger.error("PDF not found: %s", pdf_path)
        raise
    except OSError as exc:
        logger.error("Failed to open PDF %s: %s", pdf_path, exc)
        raise


def run_extraction_agent(pdf_text: str) -> ExtractionOutput:
    """
    Agent 1: Extract structured fields from raw discharge document text.

    Sends the PDF text to the LLM with a strict extraction system prompt.
    Validates the response against the ExtractionOutput Pydantic model.
    Returns the validated model on success.

    This is the HARD GATE agent — do not proceed to Agent 2 until this
    function passes on 8/10 test documents. The schema it returns is the
    contract for all downstream agents; never change field names without
    team sign-off.

    Data contract (output):
        ExtractionOutput — see dischargeiq/models/extraction.py for full schema.
        Required field: primary_diagnosis (str, never null).
        Optional scalar fields return None if not found in the document.
        All list fields return [] (never None) if nothing was extracted.

    Args:
        pdf_text: Raw text extracted from the discharge PDF via pdfplumber.
                  Should be the full document text; truncation may cause missed fields.

    Returns:
        ExtractionOutput: Validated Pydantic model containing all extracted fields.
                          Fields not found in the document are None or [].

    Raises:
        json.JSONDecodeError: If the LLM returns malformed JSON despite the prompt.
        pydantic.ValidationError: If the JSON does not satisfy the ExtractionOutput schema.
        FileNotFoundError: If agent1_system_prompt.txt is missing.
        Exception: Re-raises any unexpected LLM API error after logging.
    """
    system_prompt = _load_system_prompt()
    raw_response = _call_gemini(system_prompt, pdf_text)
    return _parse_and_validate(raw_response)
