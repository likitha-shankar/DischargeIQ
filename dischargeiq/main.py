"""
File: dischargeiq/main.py

Process entry point for uvicorn:
    uvicorn dischargeiq.main:app --host 0.0.0.0 --port 8000

All application logic has moved into focused modules:
    dischargeiq/api/app.py         — FastAPI factory + lifespan + CORS
    dischargeiq/api/routes/        — one module per resource endpoint
    dischargeiq/services/session.py — thread-safe in-memory session state
    dischargeiq/services/chat.py   — grounded patient Q&A domain logic

This file's only responsibilities are:
    1. Load environment variables from .env (must happen before app creation).
    2. Configure logging (must happen once per process).
    3. Call create_app() and bind the result to the module-level `app` symbol
       that uvicorn expects.
    4. Re-export the symbols that existing tests access via `from dischargeiq.main import ...`
       or `from dischargeiq import main as dq_main`.

Backward-compat re-exports (tests only — do not use in new code):
    _validate_uploaded_pdf  → validate_uploaded_pdf() from api/routes/analyze.py
    _store_pdf              → session_store.store_pdf()
    _set_progress           → session_store.set_progress()
    _pdf_store              → session_store._pdf           (OrderedDict)
    _pdf_store_lock         → session_store._pdf_lock      (threading.Lock)
    _simulator_store        → session_store._simulator     (OrderedDict)
    _pipeline_progress      → session_store._progress      (dict)
    _PROGRESS_TTL_SECONDS   → session_store.progress_ttl   (float)
"""

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

from dischargeiq.utils.logger import configure_logging

configure_logging()

from dischargeiq.api.app import create_app
from dischargeiq.api.routes.analyze import validate_uploaded_pdf
from dischargeiq.services.session import session_store

# ── Public app symbol (uvicorn entry point) ───────────────────────────────────
app = create_app()

# ── Backward-compat shims (consumed by existing tests) ───────────────────────
# Tests should migrate to using session_store.<method>() directly.
# These aliases will be removed once the test suite is updated.

_validate_uploaded_pdf = validate_uploaded_pdf
_store_pdf = session_store.store_pdf
_set_progress = session_store.set_progress
_pdf_store = session_store._pdf
_pdf_store_lock = session_store._pdf_lock
_simulator_store = session_store._simulator
_pipeline_progress = session_store._progress
_PROGRESS_TTL_SECONDS = session_store.progress_ttl
