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
"""

from fastapi import Request


async def get_db_pool(request: Request):
    """
    Provide the long-lived asyncpg pool from the FastAPI lifespan context.

    Returns None when DATABASE_URL is unset or the pool failed to initialise
    at startup — callers must treat None as "no persistence available" and
    proceed without saving history.

    Args:
        request: FastAPI Request object (injected automatically by Depends).

    Returns:
        asyncpg.Pool | None: The pool if initialised; None otherwise.
    """
    return getattr(request.app.state, "db_pool", None)
