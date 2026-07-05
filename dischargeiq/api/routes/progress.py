"""
api/routes/progress.py

GET /progress/{session_id} - real-time pipeline progress polling.

The Streamlit frontend polls this endpoint every ~500ms while a pipeline
is running to drive the progress bar. TTL-based eviction prevents the
in-memory progress dict from growing without bound across long server
uptimes. Each /progress response opportunistically sweeps stale entries.
"""

import asyncio
import logging

from fastapi import APIRouter

from dischargeiq.services.session import session_store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/progress/{session_id}")
async def get_progress(session_id: str):
    """
    Return real-time pipeline progress for a session.

    Sweeps stale progress entries (TTL = 600s) on each call so the
    in-memory dict does not grow unbounded during long server uptimes.

    Args:
        session_id: UUID issued by POST /analyze.

    Returns:
        dict: Progress payload with status, current_agent, agent_name, message.
              Returns {"status": "not_found", "current_agent": 0} for unknown sessions.
    """
    session_store.sweep_stale_progress()
    payload = session_store.get_progress(session_id)
    if payload is None:
        return {"status": "not_found", "current_agent": 0}
    return payload


async def cleanup_progress_after_delay(session_id: str, delay_s: float = 300.0) -> None:
    """
    Remove a progress record after a retention delay.

    Scheduled as an asyncio background task after each pipeline run so the
    progress entry is not held forever in memory. If the task is cancelled
    during server shutdown, the entry will be swept by sweep_stale_progress()
    on the next /progress read.

    Args:
        session_id: Session whose progress entry should be removed.
        delay_s:    Seconds to wait before removal. Default 300s (5 minutes).
    """
    try:
        await asyncio.sleep(delay_s)
    except asyncio.CancelledError:
        logger.info("Progress cleanup cancelled for session %s", session_id)
        raise
    session_store.pop_progress(session_id)
