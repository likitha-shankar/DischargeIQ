"""
api/routes/health.py

GET /health — liveness + lightweight dependency signals.

Returns 200 when the process is up. Includes the active LLM provider,
whether the Anthropic API key is set, and whether the database pool can
execute a simple SELECT 1. Never exposes secret values.
"""

import logging
import os

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health(request: Request):
    """
    Liveness plus dependency signals for ops / eval prep.

    Returns 200 when the process is up. Checks DB pool reachability using
    the long-lived pool from app.state (created by the lifespan context in
    api/app.py) to avoid opening a new connection per health call.

    Args:
        request: FastAPI Request — used to access app.state.db_pool.

    Returns:
        dict: status, llm_provider, anthropic_api_key_configured, database.
    """
    anthropic_set = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    database_url = os.getenv("DATABASE_URL", "").strip()

    db_pool = getattr(request.app.state, "db_pool", None)
    db_reachable: bool | None = None
    db_detail = ""

    if db_pool is not None:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_reachable = True
        except Exception as exc:
            db_reachable = False
            # Log the full exception internally; never return connection string
            # fragments, hostnames, or credentials to the caller. A generic
            # "unreachable" message is enough for ops triage — details go to logs.
            logger.error("DB health check failed: %s", exc)
            db_detail = "unreachable — see server logs"
    elif database_url:
        db_detail = "pool not initialised"
    else:
        db_detail = "not configured"

    return {
        "status": "ok",
        "llm_provider": provider,
        "anthropic_api_key_configured": anthropic_set,
        "database": {
            "configured": bool(database_url),
            "reachable": db_reachable,
            "detail": db_detail,
        },
    }
