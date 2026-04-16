"""
Agent 1 — Extraction agent (DIS-5).

Reads discharge document text (extracted via pdfplumber) and calls the LLM
with agent1_system_prompt.txt to produce JSON matching ExtractionOutput.
Validates the response with Pydantic; never fabricates field values —
missing data is returned as null or [] per the locked schema contract.

Supports multiple LLM providers via the LLM_PROVIDER env var:
  openrouter (default) — https://openrouter.ai
  openai               — https://api.openai.com
  ollama               — http://localhost:11434 (local, no key needed)

Depends on: openai, pdfplumber, pydantic v2,
            dischargeiq.models.extraction, prompts/agent1_system_prompt.txt.
"""

import json
import logging
import re
import os
import time
from pathlib import Path

import pdfplumber
from openai import OpenAI, RateLimitError
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
        str: Formatted prompt string ready to pass to the chat completions endpoint.
    """
    return (
        f"Extract all structured fields from the hospital discharge document below.\n\n"
        f"REQUIRED OUTPUT FORMAT:{_SCHEMA_BLOCK}\n"
        f"DISCHARGE DOCUMENT:\n{pdf_text}"
    )


def _is_rate_limit_error(exc: Exception) -> bool:
    """
    Return True if exc is an HTTP 429 rate-limit error from the LLM provider.

    The openai SDK raises openai.RateLimitError for HTTP 429 responses across
    all OpenAI-compatible providers (OpenRouter, OpenAI, Ollama). Using the
    typed exception avoids fragile string matching against provider-specific
    error bodies.

    Args:
        exc: The caught exception.

    Returns:
        bool: True if this is a rate-limit error worth retrying after a delay.
    """
    return isinstance(exc, RateLimitError)


# Default configuration per provider. Checked at runtime via _get_llm_client().
# Add new providers here — no other code needs to change.
_PROVIDER_DEFAULTS: dict[str, dict] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        # Free-tier model on OpenRouter. Override with LLM_MODEL in .env.
        # Use openrouter.ai/models to browse available models for your account.
        "default_model": "openai/gpt-oss-20b:free",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "ollama": {
        # Ollama exposes an OpenAI-compatible endpoint locally.
        # Override base URL via OLLAMA_BASE_URL for remote or Docker-based installs.
        "base_url": "http://localhost:11434/v1",
        "api_key_env": None,  # No real key — "ollama" is a required placeholder
        "default_model": "llama3.2",
    },
}


def _get_llm_client() -> tuple[OpenAI, str]:
    """
    Build an OpenAI-compatible client and resolve the model name from env vars.

    Reads LLM_PROVIDER (default: openrouter) to select the backend, then
    reads the provider-specific API key and base URL. LLM_MODEL overrides the
    provider default model if set.

    Supported providers:
        openrouter — https://openrouter.ai (needs OPENROUTER_API_KEY)
        openai     — https://api.openai.com (needs OPENAI_API_KEY)
        ollama     — http://localhost:11434 (no API key required)

    Returns:
        tuple[OpenAI, str]: Configured client and the resolved model name string.

    Raises:
        ValueError: If LLM_PROVIDER is set to an unrecognised value.
        KeyError: If the required API key env var for the chosen provider is missing.
    """
    provider = os.environ.get("LLM_PROVIDER", "openrouter").lower()

    if provider not in _PROVIDER_DEFAULTS:
        supported = ", ".join(_PROVIDER_DEFAULTS)
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider}'. Supported values: {supported}"
        )

    config = _PROVIDER_DEFAULTS[provider]

    # Ollama does not require a real API key; "ollama" is a required placeholder
    # so the OpenAI client constructor does not reject a None value.
    if config["api_key_env"] is None:
        api_key = "ollama"
    else:
        api_key = os.environ[config["api_key_env"]]

    # Allow Ollama base URL override for remote or Docker-based installs.
    if provider == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", config["base_url"])
    else:
        base_url = config["base_url"]

    model_name = os.environ.get("LLM_MODEL", config["default_model"])
    logger.debug(
        "LLM provider: %s | model: %s | base_url: %s", provider, model_name, base_url
    )
    return OpenAI(base_url=base_url, api_key=api_key), model_name


def _call_llm(system_prompt: str, pdf_text: str) -> str:
    """
    Send the extraction request to the configured LLM provider and return
    the raw text response.

    Provider and model are resolved from environment variables via
    _get_llm_client(). Uses the OpenAI-compatible chat completions endpoint,
    which is supported by OpenRouter, OpenAI, and Ollama.

    Retries once on HTTP 429 (rate limit) after 65s. All other errors
    propagate immediately without retry.

    Args:
        system_prompt: System instruction string from the prompt file.
        pdf_text: Raw discharge document text to be extracted.

    Returns:
        str: Raw model response text, stripped of leading/trailing whitespace.

    Raises:
        openai.RateLimitError: After the single retry is exhausted.
        openai.OpenAIError: On any other provider API error.
        ValueError: If LLM_PROVIDER is unrecognised, or the model returns None.
        KeyError: If the required API key env var for the chosen provider is missing.
    """
    client, model_name = _get_llm_client()
    user_message = _build_user_message(pdf_text)

    # Single retry on rate limit (most free-tier providers are RPM-bounded).
    # 65 seconds gives the one-minute window time to fully clear.
    _rate_limit_retry_wait_seconds = 65
    _max_retries = 1

    for attempt in range(_max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            content = response.choices[0].message.content
            # content is Optional[str] in the SDK — guard against None responses
            # from content-filtered or tool-use-only models.
            if content is None:
                raise ValueError(
                    f"LLM returned an empty response "
                    f"(provider: {os.environ.get('LLM_PROVIDER', 'openrouter')}, "
                    f"model: {model_name}). Check for content filtering."
                )
            return content.strip()
        except RateLimitError as exc:
            if attempt < _max_retries:
                logger.warning(
                    "Rate limit hit (attempt %d) — waiting %ds before retry.",
                    attempt + 1,
                    _rate_limit_retry_wait_seconds,
                )
                time.sleep(_rate_limit_retry_wait_seconds)
            else:
                logger.error("Rate limit exhausted after retry: %s", exc)
                raise
        except Exception as exc:
            logger.error("LLM API call failed: %s", exc)
            raise


def _strip_markdown_fences(raw: str) -> str:
    """
    Remove markdown code fences that LLMs sometimes wrap around JSON.

    Args:
        raw: Raw LLM response that may contain ```json ... ``` wrappers.

    Returns:
        str: Cleaned string with fences removed, ready for json.loads().
    """
    # Strip inline // comments that some models inject mid-JSON
    # (e.g. "date": "2026-03-15"  // Assuming date format...).
    # This runs before fence stripping so the regex sees the full raw string.
    raw = re.sub(r'//[^\n]*', '', raw)
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
        # Some models occasionally insert stray tokens mid-JSON on
        # table-heavy documents. This cleanup step removes non-JSON
        # lines before parsing as a last-resort fallback.
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


def _detect_low_text_density(page: object) -> bool:
    """
    Return True if the page contains fewer than 20 words.

    Pages below this threshold are likely scanned images with no extractable
    text layer. They are flagged so the caller can assess overall document quality.

    Args:
        page: A pdfplumber Page object.

    Returns:
        bool: True if the page word count is under 20.
    """
    text = page.extract_text() or ""
    return len(text.split()) < 20


def _extract_page_tables(page: object) -> str:
    """
    Extract tables from a pdfplumber page and format them as pipe-delimited rows.

    Each table row becomes one line: "cell1 | cell2 | cell3". This preserves
    medication tables that pdfplumber's standard text extraction would flatten
    into a single unreadable block.

    Args:
        page: A pdfplumber Page object.

    Returns:
        str: Pipe-delimited table rows joined by newlines, or "" if no tables found.
    """
    try:
        tables = page.extract_tables()
    except Exception as exc:  # noqa: BLE001 — pdfplumber table errors are non-fatal
        logger.warning("Table extraction failed on a page: %s", exc)
        return ""

    if not tables:
        return ""

    table_parts = []
    for table in tables:
        for row in table:
            # Replace None cells (merged/empty) with empty string before joining.
            clean_row = [cell or "" for cell in row]
            table_parts.append(" | ".join(clean_row))
    return "\n".join(table_parts)


def _extract_page_text(page: object) -> str:
    """
    Extract text from a single pdfplumber page with multi-column fallback.

    Standard extraction is attempted first. If the result looks like a scrambled
    multi-column layout — wide page, average line shorter than 40 characters —
    the extraction is retried with tighter x/y tolerances. Table content is always
    appended after the main text so medication tables are not lost.

    Args:
        page: A pdfplumber Page object.

    Returns:
        str: Combined page text including any table rows. May be empty for
             image-only pages.
    """
    text = page.extract_text() or ""

    # Multi-column detection: wide page with suspiciously short average line length.
    if page.width > 500 and text:
        lines = [line for line in text.splitlines() if line.strip()]
        avg_line_len = sum(len(line) for line in lines) / len(lines) if lines else 0
        if avg_line_len < 40:
            # Tighter tolerances group characters that belong to the same column.
            fallback = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            if len(fallback) >= len(text):
                text = fallback

    table_text = _extract_page_tables(page)
    if table_text:
        text = f"{text}\n{table_text}" if text else table_text
    return text


def _build_document_notes(pages_info: list[dict]) -> str:
    """
    Build a prepended note string when more than 30% of pages are low-density.

    The note is written in plain text so the LLM can read it and factor
    extraction confidence accordingly.

    Args:
        pages_info: List of dicts, one per processed page, each with key
                    'low_text_density' (bool).

    Returns:
        str: Warning note ending with two newlines, or "" if no anomaly detected.
    """
    total = len(pages_info)
    if total == 0:
        return ""
    low_count = sum(1 for p in pages_info if p["low_text_density"])
    if (low_count / total) > 0.30:
        return (
            "[DOCUMENT NOTE: Multiple pages appear to be scanned images with "
            "limited extractable text. OCR quality may affect extraction accuracy.]\n\n"
        )
    return ""


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all text from a PDF file using pdfplumber with real-world robustness.

    Handles multi-column layouts, embedded tables, image-heavy/scanned pages,
    documents over 50 pages, password-protected files, and corrupted PDFs.
    Returns a single string ready for the LLM extraction call.

    Per-page processing (via helpers):
        - _detect_low_text_density: flags pages with < 20 words as likely scanned.
        - _extract_page_text: standard text + multi-column fallback.
        - _extract_page_tables: appends pipe-delimited table rows.

    Document-level safeguards:
        - Truncates at 50 pages and prepends a note if the document is longer.
        - Prepends a scan-quality note if > 30% of pages are low-density.
        - Prepends a no-text note if total extracted characters < 50.

    Args:
        pdf_path: Absolute or relative path to the PDF file.

    Returns:
        str: Concatenated page text, optionally prefixed with plain-text notes
             describing any extraction anomalies the LLM should be aware of.

    Raises:
        FileNotFoundError: If the file does not exist at pdf_path.
        OSError: If the file cannot be opened due to permissions or I/O errors.
        RuntimeError: For corrupted PDFs, password-protected files, or any other
                      unexpected pdfplumber error. Message includes pdf_path and
                      the original exception type so the orchestrator can set
                      pipeline_status="partial".
    """
    _page_limit = 50
    _min_text_chars = 50

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_to_process = pdf.pages[:_page_limit]
            truncated = len(pdf.pages) > _page_limit
            pages_info: list[dict] = []
            page_texts: list[str] = []
            for page in pages_to_process:
                pages_info.append({"low_text_density": _detect_low_text_density(page)})
                page_texts.append(_extract_page_text(page))
    except FileNotFoundError:
        logger.error("PDF not found: %s", pdf_path)
        raise
    except OSError as exc:
        logger.error("Failed to open PDF %s: %s", pdf_path, exc)
        raise
    except Exception as exc:
        # Catches pdfplumber PDFSyntaxError, PDFPasswordIncorrect, and any
        # other format error. Wrapped in RuntimeError so the orchestrator
        # receives a consistent exception type with context.
        logger.error("PDF extraction failed for %s: %s", pdf_path, exc)
        raise RuntimeError(
            f"PDF extraction failed for '{pdf_path}': {type(exc).__name__}: {exc}"
        ) from exc

    document_text = "\n\n".join(page_texts).strip()
    prefix = ""

    if truncated:
        prefix += (
            "[DOCUMENT NOTE: Document exceeds 50 pages — only first 50 pages "
            "processed. Verify completeness manually.]\n\n"
        )

    prefix += _build_document_notes(pages_info)

    if len(document_text) < _min_text_chars:
        prefix += (
            "[DOCUMENT NOTE: No readable text could be extracted from this document. "
            "It may be a scanned image or corrupted file.]\n\n"
        )

    return (prefix + document_text).strip()


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
        openai.OpenAIError: Re-raises any unexpected LLM provider API error after logging.
    """
    system_prompt = _load_system_prompt()
    raw_response = _call_llm(system_prompt, pdf_text)
    return _parse_and_validate(raw_response)
