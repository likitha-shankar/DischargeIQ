"""
api/app.py

FastAPI application factory for DischargeIQ.

create_app() is the single entry point that wires together:
  - The asynccontextmanager lifespan (DB pool init/teardown)
  - CORS middleware (Streamlit origins)
  - All APIRouters from api/routes/

Separating the factory from main.py makes the app importable for testing
without triggering side effects (load_dotenv, configure_logging) that
belong only in the process entry point.

Called by:
    dischargeiq/main.py  (production entry: uvicorn dischargeiq.main:app)
    tests that need a live TestClient without a real database.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dischargeiq.api.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from dischargeiq.api.routes import analyze, chat, health, pdf, progress
from dischargeiq.db.history import get_db_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """
    Create the DB pool at startup and close it cleanly at shutdown.

    Attaches the pool to app.state.db_pool so route handlers can access it
    via request.app.state.db_pool without importing from main.py. A None
    value means DATABASE_URL is unset or the pool failed — callers must
    handle this gracefully (non-fatal; pipeline proceeds without persistence).
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        try:
            app.state.db_pool = await get_db_pool(database_url)
            logger.info("DB pool ready")
        except Exception as exc:
            logger.warning("DB pool init failed (non-fatal): %s", exc)
            app.state.db_pool = None
    else:
        app.state.db_pool = None

    yield

    if getattr(app.state, "db_pool", None) is not None:
        await app.state.db_pool.close()
        logger.info("DB pool closed")


def create_app() -> FastAPI:
    """
    Build and return the configured FastAPI application.

    Sets up the lifespan context, CORS middleware, and all route modules.
    Does NOT call load_dotenv() or configure_logging() — those belong in
    the process entry point (main.py) so they run only once per process.

    Returns:
        FastAPI: Fully configured application instance ready for uvicorn.
    """
    app = FastAPI(
        title="DischargeIQ",
        description="Multi-agent AI system for plain-language patient discharge education",
        version="0.1.0",
        lifespan=_lifespan,
    )

    # SecurityHeadersMiddleware must be outermost so headers are present on
    # every response including CORS preflight, errors, and rate-limit 429s.
    app.add_middleware(SecurityHeadersMiddleware)

    # RateLimitMiddleware before CORS so blocked requests never trigger CORS
    # processing (avoids leaking allowed-origin info to abusive clients).
    app.add_middleware(RateLimitMiddleware)

    # CORS — Streamlit frontend calls /chat from the browser.
    # In production, STREAMLIT_ORIGIN should be set to the exact Cloud Run URL
    # (e.g. https://dischargeiq-xyz.us-central1.run.app) so the browser-side
    # request is accepted only from our own UI.
    # The localhost regex is retained for local development only.
    _streamlit_origin = os.getenv("STREAMLIT_ORIGIN", "").strip()
    allow_origins = [
        "http://localhost:8501",
        "http://localhost:8502",
        "http://127.0.0.1:8501",
        "http://127.0.0.1:8502",
    ]
    if _streamlit_origin:
        allow_origins.append(_streamlit_origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        # Localhost regex only — do NOT allow all origins in production.
        # When STREAMLIT_ORIGIN is set this regex is redundant; it is kept
        # here so local dev works without setting the env var.
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Discharge-Session-Id", "Authorization"],
    )

    app.include_router(health.router)
    app.include_router(analyze.router)
    app.include_router(chat.router)
    app.include_router(pdf.router)
    app.include_router(progress.router)

    return app
