"""
utils/vision_ocr.py

Enhanced cloud document reading (opt-in scan path): transcribes photos of
discharge documents - including handwritten or scribbled notes that on-device
ML Kit cannot read reliably - using Gemini's multimodal vision through the
same OpenAI-compat client every agent uses.

Privacy contract: this is the ONLY code path where a photo crosses the wire,
and it runs solely for the opt-in "enhanced read" mobile flow (the default
scan path stays on-device). Images are processed in memory and never stored.
Same provider rule as the rest of the pipeline: synthetic/de-identified
documents only until the Vertex/BAA mode.

Dependencies: utils.llm_client. Transcription only - the model is instructed
to copy what is written, never to interpret or fill gaps (null-over-guess
extends to [illegible] markers here).
"""

import base64
import logging
import os

from dischargeiq.utils.llm_client import call_chat_with_fallback, get_llm_client

logger = logging.getLogger(__name__)

# Transcription instruction - verbatim copy, no clinical interpretation.
# Fabricating a word that is not on the paper would poison every downstream
# agent, so unreadable content must surface as an explicit marker instead.
_TRANSCRIBE_PROMPT = (
    "You are a document transcriber. Transcribe ALL text visible in this "
    "photo of a medical discharge document exactly as written, including "
    "handwritten notes. Preserve labels, numbers, doses, and line structure. "
    "Do NOT interpret, summarize, correct, or add anything. If a word is "
    "unreadable, write [illegible] in its place. Output only the transcribed "
    "text."
)


def transcribe_document_images(images: list[tuple[bytes, str]]) -> str:
    """
    Transcribe photographed document pages via the vision-capable LLM.

    One vision call per page (pages are independent and a single oversized
    multi-image call risks truncation), joined with the same [PAGE n]
    markers the on-device OCR path uses so downstream behavior is identical.

    Args:
        images: List of (raw_bytes, mime_type) tuples, one per page, in
                page order. Mime type must be an image/* type.

    Returns:
        str: Combined transcription with [PAGE n] markers.

    Raises:
        ValueError: If images is empty.
        Exception: Propagates provider errors after llm_client's own
                   retry/failover - the route maps them to HTTP 502.
    """
    if not images:
        raise ValueError("no images to transcribe")

    client, model = get_llm_client()
    provider = os.environ.get("LLM_PROVIDER", "gemini")
    pages: list[str] = []
    for index, (raw, mime) in enumerate(images, start=1):
        data_url = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        text = call_chat_with_fallback(
            client=client,
            model_name=model,
            system_prompt=_TRANSCRIBE_PROMPT,
            user_message=[
                {"type": "text", "text": f"Transcribe page {index}."},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
            max_tokens=4000,
            provider=provider,
            agent_name="vision_ocr",
            document_id=f"enhanced-scan-p{index}",
        ).strip()
        logger.info("vision_ocr page %d transcribed: %d chars", index, len(text))
        pages.append(f"[PAGE {index}]\n{text}")

    return "\n\n".join(pages)
