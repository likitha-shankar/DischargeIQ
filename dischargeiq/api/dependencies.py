"""
api/dependencies.py

FastAPI dependency providers for shared application state.

Using request.app.state keeps dependencies close to the FastAPI lifecycle
without module-level globals in routes. The db_pool is created once in the
lifespan context (api/app.py) and attached to app.state; routes receive it
via Depends() without importing main.py.

Usage in route handlers:
    from fastapi import Depends
    from dischargeiq.api.dependencies import get_db_pool

    @router.post("/analyze")
    async def analyze(request: Request, pool=Depends(get_db_pool)):
        ...

WHY THIS RETRIES
----------------
Startup is not the only chance to get a pool. Neon suspends an idle database
on the free tier and Cloud Run scales to zero, so a cold container regularly
starts while the database is still waking, times out, and sets db_pool to
None. That None used to be PERMANENT for the life of the instance: there was
no retry and no re-init, so every request that instance served afterwards ran
with no persistence.

The consequence was invisible. /health still returned "ok", the guardrail
suite still passed 9/9, and the app worked - it just silently stopped saving
quiz scores and discharge history, which meant comprehension_delta came back
None and the clinician dashboard had nothing to show. Observed in production
on 12, 19 and 25 Aug 2026.

So the pool is re-created lazily on first use when it is missing. One attempt
is made per request at most, guarded by a lock so a burst of concurrent
requests does not open several pools at once.
"""

import asyncio
import logging
import os

from fastapi import Request

logger = logging.getLogger(__name__)

# Guards concurrent re-initialisation. Without it a cold instance receiving
# several simultaneous requests would build one pool per request and leak all
# but the last.
_reinit_lock = asyncio.Lock()


async def get_db_pool(request: Request):
    """
    Provide the asyncpg pool, re-creating it if startup failed to.

    Returns None when DATABASE_URL is unset, or when re-creation also fails.
    Callers must still treat None as "no persistence available" and proceed -
    losing history must never break an analysis a patient is waiting for.

    Args:
        request: FastAPI Request object (injected automatically by Depends).

    Returns:
        asyncpg.Pool | None: The pool if available; None otherwise.
    """
    pool = getattr(request.app.state, "db_pool", None)
    if pool is not None:
        return pool

    # A MISSING attribute and an attribute set to None mean different things.
    #
    #   missing -> the lifespan never ran. That is a bare TestClient(app), and
    #              inventing a pool there would connect the test suite to the
    #              real database. It did exactly that when this first landed.
    #   None    -> the lifespan ran and pool creation failed. That is the case
    #              worth recovering from.
    #
    # Only the second is ours to fix.
    if not hasattr(request.app.state, "db_pool"):
        return None

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        # Genuinely unconfigured. Nothing to retry and nothing to warn about.
        return None

    async with _reinit_lock:
        # Re-check inside the lock: another request may have just built it.
        pool = getattr(request.app.state, "db_pool", None)
        if pool is not None:
            return pool

        # Imported here rather than at module scope to keep this module free of
        # a hard dependency on the db package for tests that never touch it.
        from dischargeiq.db.history import get_db_pool as create_pool

        try:
            # A single attempt with a short backoff. The request is waiting, so
            # this cannot use the full startup retry budget; if the database is
            # still asleep the next request tries again.
            request.app.state.db_pool = await create_pool(
                database_url, attempts=2, base_delay=0.5
            )
            logger.info("DB pool re-initialised on demand after a failed startup.")
            return request.app.state.db_pool
        except Exception as exc:  # noqa: BLE001 - persistence is never fatal
            logger.warning("On-demand DB pool re-init failed (non-fatal): %s", exc)
            return None
