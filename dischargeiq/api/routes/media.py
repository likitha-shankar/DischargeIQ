"""
api/routes/media.py

GET /media/{document_type} - serve the per-diagnosis audio explainer
(Sprint 4, Task 4.1).

Media strategy (decided Jul 2026): NotebookLM has no public API, so the team
generates ONE audio explainer per supported diagnosis manually and drops the
file into dischargeiq/media/ (see that directory's README for the workflow).
The router's document_type on PipelineResponse tells the UI which file to
request. A 404 here is NORMAL - it means "no audio for this diagnosis yet"
and every UI must degrade silently to the text-only teach-back loop
(fallback rule, Sprint 6 task 6.5). Media must never block comprehension.
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

# Preference order when several formats exist for one diagnosis. NotebookLM
# exports m4a; mp3/wav cover hand-converted or replacement files.
_EXTENSIONS = (".m4a", ".mp3", ".wav")

_MIME = {".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav"}


@router.get("/media/{document_type}")
async def get_media(document_type: str):
    """
    Return the audio explainer for one diagnosis category.

    Args:
        document_type: Router classification label (e.g. "heart_failure").

    Returns:
        FileResponse: Audio bytes with the matching MIME type.

    Raises:
        HTTPException 404: Unknown label, or no audio file generated yet for
            this diagnosis - callers treat 404 as "hide the player", never
            as an error to surface to the patient.
    """
    if document_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=404, detail="No media for this document type.")
    for ext in _EXTENSIONS:
        path = _MEDIA_DIR / f"{document_type}{ext}"
        if path.is_file():
            logger.debug("GET /media/%s - serving %s", document_type, path.name)
            return FileResponse(path, media_type=_MIME[ext])
    raise HTTPException(status_code=404, detail="Audio not generated yet for this diagnosis.")
