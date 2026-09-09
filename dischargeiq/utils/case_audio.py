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

from dischargeiq.utils.audience import AUDIENCE_PATIENT
from dischargeiq.utils.llm_client import (
    call_chat_with_fallback,
    get_llm_client,
    load_agent_prompt,
)
from dischargeiq.utils.scorer import fk_check

logger = logging.getLogger(__name__)

# Documented multi-speaker TTS model (verified hands-on, Task 1.12).
_TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
# Google Cloud Text-to-Speech, authenticated with Application Default
# Credentials - the same service account the pipeline already uses for Vertex.
# No API key exists on this path, which is the point: the previous
# implementation called the AI Studio endpoint with GOOGLE_API_KEY, a
# credential outside the BAA-covered GCP surface and one that leaked into a
# terminal log on 16 Aug from an ordinary 429.
_TTS_URL = (
    "https://texttospeech.googleapis.com/v1/text:synthesize"
)
# Two distinct prebuilt voices for the Sam/Alex dialogue.
# Cloud TTS voice per host. Two distinct Neural2 voices stand in for the
# multi-speaker voice this project does not have available.
_VOICES = {"Sam": "en-US-Neural2-D", "Alex": "en-US-Neural2-F"}
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
        # Who the hosts address. The TTS prompt reads this key directly; absent
        # or "patient" keeps the default direct-to-patient narration.
        "audience": pipeline_payload.get("audience", AUDIENCE_PATIENT),
        "care_plan": extraction,
        "what_happened": pipeline_payload.get("diagnosis_explanation", ""),
        "medications": pipeline_payload.get("medication_rationale", ""),
        "recovery": pipeline_payload.get("recovery_trajectory", ""),
        "warning_signs": pipeline_payload.get("escalation_guide", ""),
    }
    # "audience" is metadata, not narratable content, and it is always
    # populated - excluding it keeps this emptiness check meaningful.
    _NON_CONTENT_KEYS = {"care_plan", "audience"}
    if not extraction and not any(
        v for k, v in sections.items() if k not in _NON_CONTENT_KEYS
    ):
        raise ValueError("pipeline payload has no content to narrate")

    system_prompt = load_agent_prompt("tts_script_prompt.txt")
    client, model = get_llm_client()

    def _generate() -> str:
        """One script attempt. Raises when the model returns nothing usable."""
        text = call_chat_with_fallback(
            client=client,
            model_name=model,
            system_prompt=system_prompt,
            user_message=json.dumps(sections, default=str),
            max_tokens=800,
            provider=os.environ.get("LLM_PROVIDER", "gemini"),
            agent_name="tts_script",
            document_id=str(extraction.get("primary_diagnosis", "case")),
        ).strip()
        if not text or "Sam:" not in text:
            raise ValueError("model returned an unusable script (no speaker lines)")
        return text

    script = _generate()

    fk = fk_check(script)
    if not fk["passes"]:
        # Advisory, not fatal: dialogue punctuation skews FK, and the human
        # listen-through is the shipping gate. The prompt carries a 12-word
        # sentence cap which took a measured script from grade 6.6 to 2.9.
        logger.warning("TTS script FK grade %.1f exceeds threshold", fk["fk_grade"])
    return script


def _wrap_pcm_as_wav(pcm: bytes, sample_rate: int = _PCM_SAMPLE_RATE) -> bytes:
    """Wrap raw 16-bit mono PCM in a minimal WAV header."""
    return (
        b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
        + b"data" + struct.pack("<I", len(pcm)) + pcm
    )


def _dialogue_turns(script: str) -> list[tuple[str, str]]:
    """
    Split a "Sam: ... / Alex: ..." script into (speaker, line) turns.

    Lines without a recognised speaker prefix are attached to the previous
    speaker rather than dropped, so a stray continuation line is still voiced.

    Args:
        script: Dialogue text as written by build_dialogue_script.

    Returns:
        Ordered turns. Empty when the script contains no speech.
    """
    turns: list[tuple[str, str]] = []
    for raw in script.splitlines():
        line = raw.strip()
        if not line:
            continue
        speaker, sep, said = line.partition(":")
        if sep and speaker.strip() in _VOICES:
            said = said.strip()
            if said:
                turns.append((speaker.strip(), said))
        elif turns:
            turns[-1] = (turns[-1][0], f"{turns[-1][1]} {line}")
    return turns


def synthesize_dialogue_bytes(script: str) -> bytes:
    """
    Render a Sam/Alex dialogue script to WAV bytes via Google Cloud TTS.

    Each turn is synthesized with its speaker's voice and the PCM is
    concatenated, which is how the two-host format is produced without a
    multi-speaker voice: this project has none available. The result is the
    same 24 kHz mono WAV the callers already expect, so POST /media/case and
    the pre-generated per-diagnosis slots are unchanged.

    Authentication is Application Default Credentials - the runtime service
    account on Cloud Run, the developer's gcloud login locally. There is no
    API key on this path by design.

    Args:
        script: Dialogue text in "Sam: ... / Alex: ..." format.

    Returns:
        bytes: Complete WAV file contents.

    Raises:
        ValueError: If the script contains no recognisable speech.
        google.auth.exceptions.DefaultCredentialsError: If ADC is unavailable.
        requests.HTTPError: If a synthesis call fails (quota, network).
    """
    import google.auth
    import google.auth.transport.requests

    turns = _dialogue_turns(script)
    if not turns:
        raise ValueError("Dialogue script contained no speech to synthesize.")

    credentials, project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    credentials.refresh(google.auth.transport.requests.Request())
    headers = {"Authorization": f"Bearer {credentials.token}"}
    # A user-credential ADC needs a billing/quota project named explicitly;
    # a service account carries its own and ignores this.
    quota_project = os.environ.get("VERTEX_PROJECT") or project
    if quota_project:
        headers["x-goog-user-project"] = quota_project

    pcm = bytearray()
    for speaker, said in turns:
        body = {
            "input": {"text": said},
            "voice": {"languageCode": "en-US", "name": _VOICES[speaker]},
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "sampleRateHertz": _PCM_SAMPLE_RATE,
                # Slightly under normal pace: this is read by someone who has
                # just come home from hospital.
                "speakingRate": 0.95,
            },
        }
        resp = requests.post(_TTS_URL, json=body, headers=headers, timeout=120)
        resp.raise_for_status()
        chunk = base64.b64decode(resp.json()["audioContent"])
        # Cloud TTS returns a complete WAV per request; strip the 44-byte
        # header so the concatenation is one continuous stream rather than
        # several files glued together.
        pcm += chunk[44:] if chunk[:4] == b"RIFF" else chunk

    logger.info(
        "TTS audio synthesized: %d turns, %.1fs",
        len(turns), len(pcm) / _PCM_SAMPLE_RATE / 2,
    )
    return _wrap_pcm_as_wav(bytes(pcm))


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
