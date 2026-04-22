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
from dischargeiq.utils.llm_client import call_chat_with_fallback, get_llm_client

logger = logging.getLogger(__name__)

# Absolute path to the prompts directory, resolved relative to this file.
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# ── Deterministic post-processing tables ───────────────────────────────────
# LLM prompt instructions are followed inconsistently; deterministic Python
# post-processing is not. These lookup tables translate the most common
# clinical abbreviations into plain-English phrases after the LLM response
# is parsed. They are ordered by length (via sorted(..., key=len, reverse=True)
# at substitution time) so that multi-dot variants like "q.i.d." match before
# their dotless siblings like "qid".

_FREQ_NORMALIZATION_MAP: dict[str, str] = {
    # Multi-dot forms first (sorted() below handles ordering, but we keep
    # them grouped here for readability).
    "q.i.d.":        "four times daily",
    "q.h.s.":        "every night at bedtime",
    "q.d.":          "once daily",
    "b.i.d.":        "twice daily",
    "t.i.d.":        "three times daily",
    "p.r.n.":        "as needed",
    # Common dotless abbreviations.
    "qid":           "four times daily",
    "bid":           "twice daily",
    "tid":           "three times daily",
    "qhs":           "every night at bedtime",
    "prn":           "as needed",
    "qd":            "once daily",
    "od":            "once daily",
    "hs":            "every night at bedtime",
    # Interval-based abbreviations.
    "q4h":           "every 4 hours",
    "q6h":           "every 6 hours",
    "q8h":           "every 8 hours",
    "q12h":          "every 12 hours",
    # English-language variants the LLM sometimes emits verbatim; we
    # canonicalise them to the same phrases so downstream consumers see
    # a single form. NB: bare "daily" is intentionally NOT in this map —
    # the single-pass regex would otherwise re-match "daily" inside
    # already-canonical phrases like "once daily" or "twice daily",
    # producing "once once daily". Patients understand "daily" perfectly
    # well as-is, so leaving it unchanged is both safe and correct.
    "once/day":            "once daily",
    "twice/day":           "twice daily",
    "once a day":          "once daily",
    "once per day":        "once daily",
    "twice a day":         "twice daily",
    "twice per day":       "twice daily",
    "three times a day":   "three times daily",
    "three times per day": "three times daily",
    "four times a day":    "four times daily",
    "four times per day":  "four times daily",
    "at bedtime":          "every night at bedtime",
    "at hs":               "every night at bedtime",
}

_ROUTE_NORMALIZATION_MAP: dict[str, str] = {
    "p.o.":          "by mouth",
    "po":            "by mouth",
    "oral":          "by mouth",
    "i.v.":          "intravenous",
    "iv":            "intravenous",
    "sq":            "subcutaneous",
    "sc":            "subcutaneous",
    "subcut":        "subcutaneous",
    "subcutaneous":  "subcutaneous",
    "sl":            "sublingual",
    "sublingual":    "sublingual",
    "inh":           "inhaled",
    "via nebulizer": "inhaled",
    "top":           "topical",
    "topical":       "topical",
}

# Documents shorter than this word count trigger an extraction warning.
# Chosen to flag referral letters and truncated discharge summaries without
# firing on genuinely concise ER discharge notes (which typically run ~200+
# words after pdfplumber inserts whitespace for bullet structure).
_SHORT_DOC_WORD_THRESHOLD = 150


def _build_single_pass_pattern(mapping: dict[str, str]) -> "re.Pattern[str]":
    """
    Compile a single alternation regex over all keys in `mapping`, sorted
    longest-first so multi-word phrases are tried before their components.

    Args:
        mapping: The abbreviation-to-canonical lookup table.

    Returns:
        A compiled case-insensitive regex whose single match replaces exactly
        one abbreviation per position, preventing the cascade bug where
        substituting "qid" to "four times daily" then re-substituting the
        inner "daily" to "once daily" produced "four times once daily".
    """
    keys_longest_first = sorted(mapping, key=len, reverse=True)
    alternation = "|".join(re.escape(k) for k in keys_longest_first)
    # (?<![\w.]) and (?![\w]) enforce token boundaries without tripping on
    # the trailing dot in forms like "q.i.d.". re.IGNORECASE handles the
    # mixed-case strings the LLM emits ("BID", "bid", "Bid").
    return re.compile(rf"(?<![\w.])(?:{alternation})(?![\w])", flags=re.IGNORECASE)


_FREQ_PATTERN = _build_single_pass_pattern(_FREQ_NORMALIZATION_MAP)
_ROUTE_PATTERN = _build_single_pass_pattern(_ROUTE_NORMALIZATION_MAP)


def _normalize_frequency(raw: str | None) -> str | None:
    """
    Replace clinical frequency abbreviations with plain-English phrases.

    Uses a single-pass alternation regex so each position in the input is
    substituted at most once. This avoids the cascade bug where a long-form
    abbreviation expanded to a phrase (e.g. "qid" -> "four times daily")
    would have its inner tokens re-substituted on a second pass (e.g.
    "daily" -> "once daily", yielding "four times once daily"). Compound
    frequencies such as "BID PRN" are still handled because the regex
    matches each token independently in one pass — the output is
    "twice daily as needed".

    Args:
        raw: Raw frequency string as returned by the LLM. May be None for
             medications where the frequency was not documented.

    Returns:
        Normalised frequency string with abbreviations expanded, or None if
        `raw` was None. Whitespace is collapsed; non-abbreviation words are
        preserved verbatim.
    """
    if raw is None:
        return None
    text = _FREQ_PATTERN.sub(
        lambda m: _FREQ_NORMALIZATION_MAP[m.group(0).lower()], raw
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text or raw


def _normalize_route(raw: str | None) -> str | None:
    """
    Replace route-of-administration abbreviations with plain-English phrases.

    The Medication model does not expose a dedicated `route` field, but
    discharge documents frequently concatenate route and frequency into a
    single string (e.g. "PO BID", "SQ once daily"). Running this function on
    the frequency field before the frequency normaliser ensures route
    abbreviations are expanded consistently even though there is no separate
    field to hold them.

    Args:
        raw: Raw string that may embed a route abbreviation.

    Returns:
        Normalised string, or None if `raw` was None.
    """
    if raw is None:
        return None
    text = _ROUTE_PATTERN.sub(
        lambda m: _ROUTE_NORMALIZATION_MAP[m.group(0).lower()], raw
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text or raw


def _apply_medication_normalization(extraction: ExtractionOutput) -> None:
    """
    Normalise frequency strings on every medication in-place and title-case
    all-lowercase drug names.

    Route normalisation is applied first (expands "PO" to "by mouth") so the
    subsequent frequency normaliser sees a cleaner string without embedded
    route tokens. Debug-level logging records any string that changed — the
    DEBUG channel keeps the INFO session log quiet during normal runs while
    still being available for spot-checking extraction quality.

    Name casing: when the LLM returns a drug name in all-lowercase form
    (e.g. "prednisone"), title-case it to "Prednisone" so the UI renders a
    consistent medication card header regardless of how the source document
    was typeset. Names with any existing uppercase letter are left untouched,
    which preserves mixed-case drug names like "Trimethoprim-sulfamethoxazole"
    and branded names like "HydrOXYzine".

    Args:
        extraction: The validated ExtractionOutput to mutate in place.
    """
    for medication in extraction.medications:
        original_frequency = medication.frequency
        if medication.frequency is not None:
            after_route = _normalize_route(medication.frequency)
            medication.frequency = _normalize_frequency(after_route)
        if original_frequency != medication.frequency:
            logger.debug(
                "Medication '%s' frequency normalised: '%s' -> '%s'",
                medication.name,
                original_frequency,
                medication.frequency,
            )

        # Title-case all-lowercase names only; leave mixed-case names alone.
        if medication.name and medication.name == medication.name.lower():
            original_name = medication.name
            medication.name = medication.name.title()
            logger.debug(
                "Medication name title-cased: '%s' -> '%s'",
                original_name,
                medication.name,
            )


# Matches a numeric dose immediately followed by a mass/volume unit. Chosen
# units cover the discharge-med vocabulary (mg, mcg, g, IU, units, ml). The
# pattern is case-insensitive at compile time and anchors the number so
# stray integers like "5 days" do not register as doses.
_DOSE_VALUE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|iu|units|ml)\b",
    flags=re.IGNORECASE,
)

# Window (in characters) after a drug-name occurrence in which a dose value
# counts as "belonging" to that drug. 60 chars is enough to span typical
# phrasing like "Metoprolol increased from 12.5mg to 50mg twice daily"
# while staying short enough to avoid picking up unrelated downstream doses.
_DOSE_CONFLICT_WINDOW_CHARS = 60


def _check_dose_conflicts(
    raw_text: str,
    medications: list,
) -> list[str]:
    """
    Detect medications that appear with conflicting doses across sections.

    Walks the raw discharge text for each medication's name (word-boundary,
    case-insensitive) and, at every occurrence, pulls the first dose value
    found within the next _DOSE_CONFLICT_WINDOW_CHARS characters. If the
    same drug yields two or more distinct dose values across the document,
    an extraction warning is produced so downstream agents and the UI can
    surface the conflict instead of silently picking one value.

    The check is deliberately conservative:
        - Only numeric + unit tokens count (see _DOSE_VALUE_PATTERN), so
          instruction text like "for 5 days" is ignored.
        - A drug with fewer than two distinct dose values produces no
          warning — occurrences that share the same dose are expected
          (e.g. a discharge meds section and a discharge instructions
          section both stating "Metoprolol 25mg twice daily").
        - Dose values are normalised to lowercase for comparison, so
          "25mg" and "25 MG" are the same dose.

    Args:
        raw_text:    Full discharge-document text as extracted by
                     pdfplumber (the exact string sent to the LLM).
        medications: The medication list from the validated
                     ExtractionOutput, already normalised.

    Returns:
        list[str]: One warning per drug with conflicting doses. Empty
                   list when no conflicts are found. Warnings are phrased
                   as complete sentences ready for the UI.
    """
    if not raw_text or not medications:
        return []

    warnings: list[str] = []

    for medication in medications:
        name = medication.name or ""
        if not name.strip():
            continue

        # Word-boundary match on the drug name, escaped so punctuation
        # in the name (hyphens, slashes) is treated literally. For
        # multi-word names the embedded spaces still match literally.
        name_pattern = re.compile(
            rf"\b{re.escape(name)}\b",
            flags=re.IGNORECASE,
        )

        distinct_doses: list[str] = []
        distinct_doses_seen: set[str] = set()

        for match in name_pattern.finditer(raw_text):
            window_end = match.end() + _DOSE_CONFLICT_WINDOW_CHARS
            window = raw_text[match.end():window_end]

            dose_match = _DOSE_VALUE_PATTERN.search(window)
            if not dose_match:
                continue

            # Canonical form: "<number><unit>" in lowercase for dedupe.
            canonical = (
                f"{dose_match.group(1)}{dose_match.group(2).lower()}"
            )
            if canonical in distinct_doses_seen:
                continue
            distinct_doses_seen.add(canonical)
            distinct_doses.append(
                f"{dose_match.group(1)}{dose_match.group(2)}"
            )

        if len(distinct_doses) >= 2:
            dose_list = ", ".join(distinct_doses)
            warnings.append(
                f"Conflicting doses for {name}: found "
                f"{dose_list} in document. Verify against original."
            )

    return warnings


def _short_document_warning(raw_text: str) -> list[str]:
    """
    Return a single-element list containing a short-document warning when
    the extracted text is below the word-count threshold, or an empty list.

    Deterministic enforcement of the "unusually short document" rule that the
    system prompt describes. Moving this check into Python guarantees the
    warning fires regardless of whether the LLM obeyed the prompt on a given
    request.

    Args:
        raw_text: The full extracted document text that will be sent to the
                  LLM (after pdfplumber and any [DOCUMENT NOTE] prefixes).

    Returns:
        [warning_string] when word_count < _SHORT_DOC_WORD_THRESHOLD,
        else []. The warning is phrased as a complete sentence so it can be
        surfaced directly in the UI without additional formatting.
    """
    word_count = len(raw_text.split())
    if word_count < _SHORT_DOC_WORD_THRESHOLD:
        return [
            f"This document is unusually short ({word_count} words). "
            "It may be incomplete or missing key discharge sections. "
            "Verify all fields manually."
        ]
    return []


# JSON schema description injected into every user message so the model
# knows the exact field names, types, and null-vs-empty rules.
_SCHEMA_BLOCK = """
Return a single JSON object with these fields (no extra keys, no commentary):

{
  "patient_name":             string or null,
  "discharge_date":           string or null  (e.g. "2024-03-15"),
  "primary_diagnosis":        string          (REQUIRED — never null),
  "primary_diagnosis_source": {
    "page": integer (1-indexed page number where the diagnosis appears),
    "text": "the exact sentence or line from the PDF that states the primary diagnosis"
  },
  "secondary_diagnoses":      array of strings ([] if none),
  "procedures_performed":     array of strings ([] if none),
  "medications": [
    {
      "name":      string (REQUIRED),
      "dose":      string or null,
      "frequency": string or null,
      "duration":  string or null,
      "status":    "new" | "changed" | "continued" | "discontinued" | null,
      "source": {
        "page": integer (1-indexed page number where this medication appears),
        "text": "the exact sentence or bullet from the PDF that lists this medication"
      }
    }
  ],
  "follow_up_appointments": [
    {
      "provider":  string or null,
      "specialty": string or null,
      "date":      string or null,
      "reason":    string or null,
      "source": {
        "page": integer (1-indexed page number where this appointment appears),
        "text": "the exact sentence or line from the PDF that mentions this appointment"
      }
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


# Provider routing is centralised in dischargeiq/utils/llm_client.py.
# All agents use get_llm_client() so changing LLM_PROVIDER in .env
# switches every agent at once without touching agent code.
_get_llm_client = get_llm_client


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
    provider = os.environ.get("LLM_PROVIDER", "openrouter").lower()
    user_message = _build_user_message(pdf_text)
    try:
        return call_chat_with_fallback(
            client=client,
            model_name=model_name,
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=4096,
            provider=provider,
            agent_name="Agent 1",
            document_id="extraction",
        )
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
    Return True if the page contains fewer than 5 words.

    The previous threshold of 20 words produced false positives on short but
    perfectly text-extractable PDFs (e.g. a 3-line ER discharge note with
    ~37 words on one page). A real scanned/image page typically exposes no
    extractable words at all — at most a handful of artifacts from stamps
    or OCR noise — so 5 words is a sharper signal for the true failure mode
    we care about (no text layer to extract).

    Pages below this threshold are combined with the document-level text
    length check in _build_document_notes() to decide whether to prepend a
    scan-quality note.

    Args:
        page: A pdfplumber Page object.

    Returns:
        bool: True if the page word count is under 5.
    """
    text = page.extract_text() or ""
    return len(text.split()) < 5


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


def _build_document_notes(
    pages_info: list[dict],
    document_text: str,
) -> str:
    """
    Build a prepended note string when the document genuinely looks scanned.

    Two conditions must both hold before the scan note is emitted:
        1. More than 30% of processed pages are low-density (see
           _detect_low_text_density — now thresholded at <5 words).
        2. The whole document's average is below 5 words per page.

    Requiring the document-level average prevents the scan note from firing
    on short text-only discharge notes (e.g. a 3-line ER summary where one
    page is "dense" by ratio but the document is just genuinely short). A
    real scanned document will have nearly zero extractable words per page
    across the board.

    The note is written in plain text so the LLM can read it and factor
    extraction confidence accordingly.

    Args:
        pages_info:    List of dicts, one per processed page, each with key
                       'low_text_density' (bool).
        document_text: The concatenated text of all processed pages, used
                       to compute the document-wide words-per-page average.

    Returns:
        str: Warning note ending with two newlines, or "" if the document
             does not meet the scan-quality criteria above.
    """
    total = len(pages_info)
    if total == 0:
        return ""

    low_count = sum(1 for p in pages_info if p["low_text_density"])
    low_density_ratio = low_count / total

    # Document-wide words-per-page average. Protects against a single short
    # page triggering the warning on an otherwise text-rich document.
    total_words = len(document_text.split()) if document_text else 0
    avg_words_per_page = total_words / total

    if low_density_ratio > 0.30 and avg_words_per_page < 5:
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

    # Prepend [PAGE N] markers so the LLM knows which page each passage is on.
    # This is the signal Agent 1 uses to populate source.page correctly.
    marked_pages = [f"[PAGE {i}]\n{text}" for i, text in enumerate(page_texts, start=1)]
    document_text = "\n\n".join(marked_pages).strip()
    prefix = ""

    if truncated:
        prefix += (
            "[DOCUMENT NOTE: Document exceeds 50 pages — only first 50 pages "
            "processed. Verify completeness manually.]\n\n"
        )

    prefix += _build_document_notes(pages_info, document_text)

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
    # Pre-LLM deterministic checks. These run before the LLM is invoked so
    # the resulting warnings are guaranteed regardless of whether the model
    # obeyed the prompt-level instructions on this request.
    pre_warnings = _short_document_warning(pdf_text)

    system_prompt = _load_system_prompt()
    raw_response = _call_llm(system_prompt, pdf_text)
    result = _parse_and_validate(raw_response)

    # Post-LLM deterministic normalisation — route and frequency abbreviations
    # are expanded on every medication entry so downstream agents see
    # consistent plain-English text regardless of how the LLM formatted the
    # discharge source.
    _apply_medication_normalization(result)

    # Cross-section dose consistency check. Runs after normalisation so the
    # warning uses the canonical drug name, and runs against the raw PDF
    # text (not the LLM's JSON) so conflicts hidden inside narrative prose
    # are still detected even if the LLM collapsed them into a single
    # medications entry.
    dose_conflict_warnings = _check_dose_conflicts(pdf_text, result.medications)

    # Merge pre-warnings, dose-conflict warnings, and LLM-added warnings.
    # A set-based dedupe keeps the list clean if the LLM happened to emit
    # the same sentence independently.
    existing_warnings = set(result.extraction_warnings)
    for warning in (*pre_warnings, *dose_conflict_warnings):
        if warning not in existing_warnings:
            result.extraction_warnings.append(warning)
            existing_warnings.add(warning)

    # Log a structured completion summary so the orchestrator log shows
    # extraction quality at a glance without needing to parse the full output.
    logger.info(
        "Agent 1 complete — diagnosis: '%s', meds: %d, follow-ups: %d, warnings: %d",
        result.primary_diagnosis,
        len(result.medications),
        len(result.follow_up_appointments),
        len(result.extraction_warnings),
    )

    for warning in result.extraction_warnings:
        # Emit each extraction warning at WARNING level so it surfaces in the
        # session log even when the overall extraction succeeded.
        logger.warning("Agent 1 extraction warning: %s", warning)

    return result
