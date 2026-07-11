"""
api/routes/media.py

GET  /media/{document_type}         - per-diagnosis AUDIO explainer (podcast).
GET  /media/{document_type}/video   - per-diagnosis VIDEO explainer.
POST /media/case                    - per-CASE TTS explainer from the
                                      patient's own pipeline output.

Per-diagnosis files (Task 4.1): NotebookLM has no public API, so one Audio
Overview and optionally one Video Overview per supported diagnosis is
generated manually and dropped into dischargeiq/media/ (see that directory's
README). The router's document_type on PipelineResponse tells the UI which
files to request.

Per-case audio (Task 2.5, serving decision D-5 in docs/ISSUES_AND_IDEAS.md):
generated ON DEMAND via Gemini TTS - the client posts the pipeline payload it
already holds (stateless, like /chat and /quiz), receives WAV bytes once, and
caches them on device. Rejected alternatives: pipeline-time pre-generation
(burns quota + latency on uploads nobody listens to) and a server-side session
cache (process-local store problem, see ISSUES I-8). Gated by the
CASE_AUDIO_ENABLED env flag, default OFF until the Task 4.2 human
listen-through approves the prompt/voice mechanism (ISSUES I-1).

A 404 from any endpoint is NORMAL - it means "no audio available" and every
UI must degrade silently to the text-only teach-back loop (fallback rule,
Sprint 6 task 6.5). Media never blocks comprehension.
"""

import asyncio
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from dischargeiq.api.schemas import CaseAudioRequest
from dischargeiq.utils.case_audio import (
    build_dialogue_script,
    synthesize_dialogue_bytes,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_MEDIA_DIR = Path(__file__).resolve().parent.parent.parent / "media"

# Boundary validation: document_type is a path segment, so it MUST be checked
# against the closed set of router labels - never interpolated into a path
# raw. Mirrors _VALID_TYPES in agents/router_agent.py ("unknown" excluded:
# an unclassified document has no matching explainer by definition).
_ALLOWED_TYPES = frozenset(
    {"heart_failure", "copd", "diabetes", "hip_replacement", "surgical"}
)

# Preference order per media kind. NotebookLM exports m4a audio and mp4
# video; the extra extensions cover hand-converted or replacement files.
_KIND_EXTENSIONS = {
    "audio": (".m4a", ".mp3", ".wav"),
    "video": (".mp4", ".webm"),
}

_MIME = {
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


def _serve(document_type: str, kind: str) -> FileResponse:
    """
    Locate and serve one media file for a diagnosis, or raise 404.

    Args:
        document_type: Router classification label (e.g. "heart_failure").
        kind: "audio" or "video" - selects the extension preference list.

    Returns:
        FileResponse: Media bytes with the matching MIME type.

    Raises:
        HTTPException 404: Unknown label, or no file of this kind generated
            yet - callers treat 404 as "hide the player", never as an error
            to surface to the patient.
    """
    if document_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=404, detail="No media for this document type.")
    for ext in _KIND_EXTENSIONS[kind]:
        path = _MEDIA_DIR / f"{document_type}{ext}"
        if path.is_file():
            logger.debug("GET /media/%s (%s) - serving %s", document_type, kind, path.name)
            return FileResponse(path, media_type=_MIME[ext])
    raise HTTPException(
        status_code=404, detail=f"{kind.capitalize()} not generated yet for this diagnosis."
    )


@router.get("/media/{document_type}")
async def get_media_audio(document_type: str):
    """Audio (podcast) explainer. Path kept short for existing clients."""
    return _serve(document_type, "audio")


@router.get("/media/{document_type}/video")
async def get_media_video(document_type: str):
    """Video explainer - same fallback contract as audio."""
    return _serve(document_type, "video")


def _case_audio_enabled() -> bool:
    """Feature flag, read per request so tests and ops can flip it live."""
    return os.environ.get("CASE_AUDIO_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


@router.post("/media/case")
async def generate_case_audio(request: CaseAudioRequest):
    """
    Generate the per-case two-host audio explainer for one session.

    Two model calls (script LLM + Gemini TTS), run in a worker thread since
    both are synchronous. The client caches the returned WAV - the server
    keeps nothing, so repeated presses of "play" must NOT re-post.

    Raises:
        HTTPException 404: Feature flag off - clients treat this exactly like
            "no per-diagnosis file" and fall back to text (Task 6.5 contract).
        HTTPException 422: Payload has no narratable content.
        HTTPException 502: Script or TTS generation failed (quota, network).
    """
    if not _case_audio_enabled():
        # Same semantics as a missing media file: hide the player, show text.
        raise HTTPException(status_code=404, detail="Per-case audio is not enabled.")
    logger.info("POST /media/case - session: %s", request.session_id)
    try:
        script = await asyncio.to_thread(build_dialogue_script, request.pipeline_payload)
        wav = await asyncio.to_thread(synthesize_dialogue_bytes, script)
    except ValueError as exc:
        # Empty payload or unusable script - the client sent nothing to narrate.
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # requests.HTTPError, timeouts - degrade, never 500
        logger.error("Per-case audio failed for '%s': %s", request.session_id, exc)
        raise HTTPException(
            status_code=502,
            detail="Audio is unavailable right now. The written summary has everything.",
        )
    return Response(content=wav, media_type="audio/wav")
