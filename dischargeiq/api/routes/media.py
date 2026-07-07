"""
api/routes/media.py

GET /media/{document_type}         - per-diagnosis AUDIO explainer (podcast).
GET /media/{document_type}/video   - per-diagnosis VIDEO explainer.

Sprint 4, Task 4.1. NotebookLM has no public API, so the team generates one
Audio Overview (podcast) and optionally one Video Overview per supported
diagnosis manually and drops the files into dischargeiq/media/ (see that
directory's README for the workflow and filenames). The router's
document_type on PipelineResponse tells the UI which files to request.

A 404 from either endpoint is NORMAL - it means "not generated yet for this
diagnosis" and every UI must degrade silently to the text-only teach-back
loop (fallback rule, Sprint 6 task 6.5). Media never blocks comprehension.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

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
