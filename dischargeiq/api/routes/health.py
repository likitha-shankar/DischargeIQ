"""
api/routes/health.py

GET /health - liveness + lightweight dependency signals.

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
        request: FastAPI Request - used to access app.state.db_pool.

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
            # "unreachable" message is enough for ops triage - details go to logs.
            logger.error("DB health check failed: %s", exc)
            db_detail = "unreachable - see server logs"
    elif database_url:
        db_detail = "pool not initialised"
    else:
        db_detail = "not configured"

    # A configured database that is not working is DEGRADED, not ok.
    #
    # This endpoint used to return "ok" in that case, with the problem visible
    # only in database.detail. Between 12 and 25 Aug 2026 production ran for
    # days with no pool: quiz scores were not persisted, discharge history was
    # not written, comprehension_delta came back None and the clinician
    # dashboard had no data - while /health said ok and the guardrail suite
    # passed 9/9. Nothing is monitoring a nested detail string; things monitor
    # status. Saying ok when persistence is dead is how three weeks passed
    # without anyone noticing.
    #
    # Still HTTP 200: the service genuinely can analyse documents without a
    # database, so this must not take an instance out of rotation. The word is
    # for whoever reads it, not for the load balancer.
    # Only claim degraded when the app actually tried and failed. A bare
    # TestClient never runs the lifespan, so app.state.db_pool is absent rather
    # than None, and reporting that as degraded would make every API test fail
    # for a condition that does not exist outside the harness.
    lifespan_ran = hasattr(request.app.state, "db_pool")
    db_broken = bool(database_url) and lifespan_ran and db_reachable is not True
    status = "degraded" if db_broken else "ok"

    payload = {
        "status": status,
        "llm_provider": provider,
        "anthropic_api_key_configured": anthropic_set,
        "database": {
            "configured": bool(database_url),
            "reachable": db_reachable,
            "detail": db_detail,
        },
    }
    if db_broken:
        # Name the consequence, not just the fault. "pool not initialised"
        # tells an operator nothing about what the patient loses.
        payload["degraded_reason"] = (
            "Database unavailable: quiz scores, comprehension deltas and "
            "discharge history are not being saved. Analysis still works."
        )
        logger.warning("Health check reporting degraded: %s", db_detail)
    return payload
