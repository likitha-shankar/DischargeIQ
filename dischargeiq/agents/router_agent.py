"""
agents/router_agent.py

Supervisor/Router Agent — Sprint 1, Task 1.3.
Owner: Likitha Shankar

Reads raw discharge document text (first ~2000 characters are sufficient for
classification) and classifies it into one of five supported diagnosis categories
or "unknown". Returns a RouterOutput dict that the orchestrator uses to:
  1. Tag the PipelineResponse with document_type for analytics/logging.
  2. Short-circuit the pipeline early when should_process=False (not a discharge doc).

This agent is intentionally lightweight — it uses a small token budget and a
truncated document slice. Full extraction is Agent 1's job. The router only needs
enough context to classify document type and gate obviously wrong inputs.

LLM provider: inherits from LLM_PROVIDER / LLM_MODEL in .env via get_llm_client().
Prompt: dischargeiq/prompts/router_system_prompt.txt

Data contract:
    Input:  str — raw PDF text (full text; internally truncated to _CLASSIFY_CHARS)
    Output: dict with keys:
                document_type (str)   — one of the 6 classification labels
                confidence    (float) — 0.0–1.0
                should_process (bool) — False only when doc is clearly not a discharge
                reason        (str)   — one-sentence human-readable explanation

Dependencies:
    - dischargeiq.utils.llm_client (get_llm_client, load_agent_prompt, call_chat_with_fallback)

Called by: dischargeiq.pipeline.orchestrator._run_pipeline_internal (before Agent 1)
"""

import json
import logging
import os
import re

from dischargeiq.utils.llm_client import (
    call_chat_with_fallback,
    get_llm_client,
    load_agent_prompt,
)

logger = logging.getLogger(__name__)

# Only the first N chars matter for document type classification.
# A real discharge summary always identifies the diagnosis in the header/summary.
_CLASSIFY_CHARS = 2000

# Max tokens for the classification response — JSON fits comfortably under 100.
_MAX_TOKENS = 150

# Valid document_type values; any LLM response outside this set is clamped to "unknown".
_VALID_TYPES = frozenset(
    {"heart_failure", "copd", "diabetes", "hip_replacement", "surgical", "unknown"}
)

# Safe fallback returned when the LLM call fails or returns malformed JSON.
_FALLBACK: dict = {
    "document_type": "unknown",
    "confidence": 0.0,
    "should_process": True,
    "reason": "Router classification unavailable — pipeline will attempt full extraction.",
}


def run_router_agent(pdf_text: str) -> dict:
    """
    Classify a discharge document and decide whether the pipeline should process it.

    Truncates the input to _CLASSIFY_CHARS before sending to the LLM — the
    document type is always declared near the top of a real discharge summary.
    On any failure (network, parse, unexpected schema) returns _FALLBACK with
    should_process=True so the pipeline continues rather than silently dropping
    a real discharge document.

    Args:
        pdf_text: Full raw text extracted from the uploaded PDF. May be empty if
                  pdfplumber found no text (scanned image PDF, password-locked, etc.).

    Returns:
        dict with keys: document_type, confidence, should_process, reason.
    """
    if not pdf_text or not pdf_text.strip():
        logger.warning("Router: empty PDF text — returning fallback with should_process=True")
        return {**_FALLBACK, "reason": "Empty document text — Agent 1 will handle extraction failure."}

    provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    client, model = get_llm_client()
    system_prompt = load_agent_prompt("router_system_prompt.txt")

    # Truncate to classification window.
    document_slice = pdf_text.strip()[:_CLASSIFY_CHARS]
    user_message = f"Classify this discharge document:\n\n{document_slice}"

    try:
        raw = call_chat_with_fallback(
            client=client,
            model_name=model,
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=_MAX_TOKENS,
            provider=provider,
            agent_name="RouterAgent",
            document_id="router",
        )

        # Strip any accidental markdown fences the LLM wraps around JSON.
        raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        parsed = json.loads(raw)

        doc_type = str(parsed.get("document_type", "unknown")).lower()
        if doc_type not in _VALID_TYPES:
            logger.warning("Router: unexpected document_type %r — clamping to 'unknown'", doc_type)
            doc_type = "unknown"

        confidence = float(parsed.get("confidence", 0.0))
        should_process = bool(parsed.get("should_process", True))
        reason = str(parsed.get("reason", ""))

        result = {
            "document_type": doc_type,
            "confidence": round(confidence, 3),
            "should_process": should_process,
            "reason": reason,
        }
        logger.info(
            "Router: type=%s confidence=%.2f should_process=%s | %s",
            doc_type, confidence, should_process, reason,
        )
        return result

    except json.JSONDecodeError as exc:
        logger.warning("Router: JSON parse failed (%s) — using fallback", exc)
        return _FALLBACK
    except Exception as exc:
        logger.warning("Router: classification failed (%s) — using fallback", exc)
        return _FALLBACK
