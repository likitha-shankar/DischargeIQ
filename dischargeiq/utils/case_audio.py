"""
utils/case_audio.py

Per-case audio explainer prototype (Task 2.5, decided by the Task 1.12
NotebookLM findings): the patient's own pipeline output becomes a short
two-host dialogue script (one text-LLM call), which Gemini TTS renders as
two-speaker audio (one REST call). Output is a WAV file the existing
GET /media endpoints already know how to serve - no serving changes needed.

Dependencies: utils.llm_client (script generation), utils.scorer (FK gate),
requests (TTS REST). The TTS model is separate from the chat models, so its
quota does not compete with the pipeline's.

Safety: the script inherits the hard rules via the system prompt (grounded
only in the provided plan, never medication-change advice) and is FK-checked
like any other agent output. Any audio shipped to patients still requires
the Task 4.2 human listen-through first.
"""

import base64
import json
import logging
import os
import struct
from pathlib import Path

import requests

from dischargeiq.utils.llm_client import (
    call_chat_with_fallback,
    get_llm_client,
    load_agent_prompt,
    require_provider_api_key,
)
from dischargeiq.utils.scorer import fk_check

logger = logging.getLogger(__name__)

# Documented multi-speaker TTS model (verified hands-on, Task 1.12).
_TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
_TTS_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)
# Two distinct prebuilt voices for the Sam/Alex dialogue.
_VOICES = {"Sam": "Kore", "Alex": "Puck"}
_PCM_SAMPLE_RATE = 24000  # Gemini TTS returns 24 kHz 16-bit mono PCM


def build_dialogue_script(pipeline_payload: dict) -> str:
    """
    Generate the two-host dialogue script from one pipeline output.

    Sends the extraction and the four patient-facing texts to the chat LLM
    with the TTS script system prompt. The script is FK-checked; a failing
    grade logs a warning but does not raise - the listen-through (Task 4.2)
    is the final human gate before any audio ships.

    Args:
        pipeline_payload: A PipelineResponse dict (e.g. one file from
            evaluation/corpus_outputs/, or a live /analyze response).

    Returns:
        str: Dialogue script in "Sam: ... / Alex: ..." line format.

    Raises:
        ValueError: If the payload has no usable content, or the model
            returns an empty script.
    """
    extraction = pipeline_payload.get("extraction") or {}
    sections = {
        "care_plan": extraction,
        "what_happened": pipeline_payload.get("diagnosis_explanation", ""),
        "medications": pipeline_payload.get("medication_rationale", ""),
        "recovery": pipeline_payload.get("recovery_trajectory", ""),
        "warning_signs": pipeline_payload.get("escalation_guide", ""),
    }
    if not extraction and not any(v for k, v in sections.items() if k != "care_plan"):
        raise ValueError("pipeline payload has no content to narrate")

    system_prompt = load_agent_prompt("tts_script_prompt.txt")
    client, model = get_llm_client()
    script = call_chat_with_fallback(
        client=client,
        model_name=model,
        system_prompt=system_prompt,
        user_message=json.dumps(sections, default=str),
        max_tokens=800,
        provider=os.environ.get("LLM_PROVIDER", "gemini"),
        agent_name="tts_script",
        document_id=str(extraction.get("primary_diagnosis", "case")),
    ).strip()
    if not script or "Sam:" not in script:
        raise ValueError("model returned an unusable script (no speaker lines)")

    fk = fk_check(script)
    if not fk["passes"]:
        # Advisory, not fatal: dialogue punctuation skews FK; the human
        # listen-through is the shipping gate.
        logger.warning("TTS script FK grade %.1f exceeds threshold", fk["fk_grade"])
    return script


def _wrap_pcm_as_wav(pcm: bytes, sample_rate: int = _PCM_SAMPLE_RATE) -> bytes:
    """Wrap raw 16-bit mono PCM in a minimal WAV header."""
    return (
        b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
        + b"data" + struct.pack("<I", len(pcm)) + pcm
    )


def synthesize_dialogue_bytes(script: str) -> bytes:
    """
    Render a Sam/Alex dialogue script to WAV bytes via Gemini TTS.

    One multi-speaker generateContent call; the returned 24 kHz PCM is
    wrapped as WAV. This is the serving primitive: POST /media/case returns
    these bytes directly (on-demand model, decision D-5), and the CLI wraps
    them in a file for the pre-generated per-diagnosis slots.

    Args:
        script: Dialogue text in "Sam: ... / Alex: ..." format.

    Returns:
        bytes: Complete WAV file contents.

    Raises:
        ValueError: If GOOGLE_API_KEY is missing.
        requests.HTTPError: If the TTS call fails (quota, model, network).
    """
    # Validates presence with a clear ValueError; the key itself comes from env.
    require_provider_api_key("gemini")
    api_key = os.environ["GOOGLE_API_KEY"].strip()
    body = {
        "contents": [{"parts": [{"text": "TTS the following conversation, warm and calm:\n" + script}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "multiSpeakerVoiceConfig": {
                    "speakerVoiceConfigs": [
                        {"speaker": name, "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}
                        for name, voice in _VOICES.items()
                    ]
                }
            },
        },
    }
    resp = requests.post(
        _TTS_URL.format(model=_TTS_MODEL, key=api_key),
        json=body,
        timeout=180,
    )
    resp.raise_for_status()
    part = resp.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
    pcm = base64.b64decode(part["data"])
    logger.info("TTS audio synthesized (%.1fs)", len(pcm) / _PCM_SAMPLE_RATE / 2)
    return _wrap_pcm_as_wav(pcm)


def synthesize_dialogue(script: str, out_path: str | Path) -> Path:
    """
    Render a dialogue script to a WAV file (CLI / pre-generated slots).

    Thin file wrapper around synthesize_dialogue_bytes - see that function
    for the TTS contract and raised exceptions.

    Args:
        script: Dialogue text in "Sam: ... / Alex: ..." format.
        out_path: Destination file path; parent directories are created.

    Returns:
        Path: The written WAV file.
    """
    wav = synthesize_dialogue_bytes(script)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(wav)
    logger.info("TTS audio written: %s", out)
    return out
