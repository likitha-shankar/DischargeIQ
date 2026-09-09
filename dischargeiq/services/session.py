"""
services/session.py

SessionStore: thread-safe, bounded in-memory store for per-upload session data.

Encapsulates all mutable shared state that previously lived as module-level
globals in main.py (_pdf_store, _simulator_store, _pipeline_progress, and
three threading.Lock objects). Moving state into a class makes it:
  - injectable (tests can instantiate a fresh store per test)
  - replaceable (swap for Redis-backed store without touching routes)
  - auditable (all mutations go through typed methods, not dict literals)

This module also exports a process-level singleton `session_store` used by
the FastAPI routes. Tests should access state via the public methods, not
by poking at the private _pdf / _simulator / _progress dicts.

Known limitation: all stores are process-local. Under Cloud Run with
max-instances > 1, a GET may land on a different instance than the POST
that wrote the data. Long-term fix: GCS or Redis for PDF/simulator stores.
"""

import logging
import threading
import os
import time
import uuid
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger(__name__)

# Defaults - match the values previously hard-coded in main.py.
_PDF_STORE_MAX = 50

#: How long a stored PDF stays fetchable, in seconds (default 2 hours).
#:
#: GET /pdf/{session_id} is a CAPABILITY URL - the session id is the only
#: thing protecting the document, because the Streamlit viewer embeds it in an
#: <iframe> and a browser iframe cannot send an Authorization header. A UUID4
#: is unguessable, but without an expiry the capability lives until LRU
#: pressure evicts it, which on a quiet instance is indefinitely.
#:
#: Bounding it turns "forever unless busy" into "two hours", which is longer
#: than any session a patient actually has and short enough that a leaked URL
#: stops working. The real fix is a signed short-lived token in the query
#: string; this is the cheap half of it.
_PDF_TTL_SECONDS = float(os.environ.get("PDF_TTL_SECONDS", 2 * 60 * 60))
_PROGRESS_TTL_SECONDS = 600.0


class SessionStore:
    """
    Thread-safe, bounded in-memory store for three per-upload data types.

    Thread safety:
        Separate locks per data structure to minimise contention between PDF
        reads, simulator reads, and progress writes. A shared lock would
        serialise all three; separate locks let them proceed in parallel.

    LRU eviction:
        The PDF store is capped at _PDF_STORE_MAX entries. When the cap is
        reached, the oldest entry (first inserted) is evicted, and its
        corresponding simulator entry is also removed to avoid orphaned data.
    """

    def __init__(self) -> None:
        self._pdf: OrderedDict[str, bytes] = OrderedDict()
        self._simulator: OrderedDict[str, dict] = OrderedDict()
        self._context: OrderedDict[str, dict] = OrderedDict()
        self._result_by_hash: OrderedDict[str, dict] = OrderedDict()
        self._progress: dict[str, dict] = {}
        self._pdf_lock = threading.Lock()
        self._simulator_lock = threading.Lock()
        self._context_lock = threading.Lock()
        self._result_lock = threading.Lock()
        self._progress_lock = threading.Lock()

    # ── PDF store ─────────────────────────────────────────────────────────────

    def store_pdf(self, pdf_bytes: bytes, session_id: Optional[str] = None) -> str:
        """
        Store PDF bytes under a UUID key, evicting the oldest entry when at capacity.

        When the store reaches pdf_store_max, the oldest PDF is evicted and its
        corresponding simulator entry is also removed so the two stores stay
        consistent without a separate garbage-collection pass.

        Args:
            pdf_bytes:  Raw PDF bytes to store.
            session_id: Caller-supplied UUID. A new UUID is generated when None.

        Returns:
            str: The session key used for later retrieval via get_pdf().
        """
        session_id = session_id or str(uuid.uuid4())
        with self._pdf_lock:
            if len(self._pdf) >= _PDF_STORE_MAX:
                old_sid, _ = self._pdf.popitem(last=False)
                with self._simulator_lock:
                    self._simulator.pop(old_sid, None)
            self._pdf[session_id] = (pdf_bytes, time.time())
        # The session id is a capability: anyone holding it can fetch the
        # document. Logging it puts a live credential into Cloud Logging,
        # where it can be replayed for as long as the entry survives. Only the
        # size is recorded.
        logger.debug("PDF stored - %d bytes", len(pdf_bytes))
        return session_id

    def get_pdf(self, session_id: str, now: Optional[float] = None) -> Optional[bytes]:
        """
        Return stored PDF bytes, or None when unknown, evicted or expired.

        Args:
            session_id: UUID returned by store_pdf().
            now: Reference timestamp, for tests. Uses time.time() when None.

        Returns:
            bytes: Raw PDF bytes, or None if the session was never stored,
            was evicted by LRU pressure, or has passed _PDF_TTL_SECONDS.

        Note:
            An expired entry is DELETED here rather than merely hidden. The
            session id is a capability URL - it is the only thing protecting
            the document - so leaving the bytes in memory after the capability
            stops working keeps patient data alive for no benefit.
        """
        current = time.time() if now is None else now
        with self._pdf_lock:
            entry = self._pdf.get(session_id)
            if entry is None:
                return None
            pdf_bytes, stored_at = entry
            if current - stored_at > _PDF_TTL_SECONDS:
                del self._pdf[session_id]
                with self._simulator_lock:
                    self._simulator.pop(session_id, None)
                logger.info("PDF session expired after %.0fs", current - stored_at)
                return None
            return pdf_bytes

    # ── Simulator store ───────────────────────────────────────────────────────

    def store_simulator(self, session_id: str, payload: dict) -> None:
        """
        Store Agent 6 model_dump() output for a session.

        Args:
            session_id: The session key associated with this pipeline run.
            payload:    PatientSimulatorOutput.model_dump() dict from Agent 6.
        """
        with self._simulator_lock:
            self._simulator[session_id] = payload

    def get_simulator(self, session_id: str) -> Optional[dict]:
        """
        Return serialized PatientSimulatorOutput, or None if missing.

        Args:
            session_id: UUID returned by POST /analyze as pdf_session_id.

        Returns:
            dict | None: model_dump() from Agent 6, or None if not stored.
        """
        with self._simulator_lock:
            return self._simulator.get(session_id)

    # ── Chat context store ────────────────────────────────────────────────────

    def store_context(self, session_id: str, payload: dict) -> None:
        """
        Store the PipelineResponse dict for a session so POST /chat can ground
        answers without the client re-uploading ~17KB of context per message.

        Capped at _PDF_STORE_MAX entries with the same oldest-first eviction as
        the PDF store; an evicted session simply falls back to the client
        re-sending pipeline_context.

        Args:
            session_id: The session key associated with this pipeline run.
            payload:    PipelineResponse.model_dump() dict from /analyze.
        """
        with self._context_lock:
            if len(self._context) >= _PDF_STORE_MAX:
                self._context.popitem(last=False)
            self._context[session_id] = payload

    def get_context(self, session_id: str) -> Optional[dict]:
        """
        Return the stored PipelineResponse dict, or None if missing/evicted.

        Args:
            session_id: UUID returned by POST /analyze as pdf_session_id.

        Returns:
            dict | None: PipelineResponse dict, or None if not stored.
        """
        with self._context_lock:
            return self._context.get(session_id)

    # ── Pipeline result cache (keyed by document hash) ────────────────────────

    def store_result_for_hash(self, document_hash: str, payload: dict) -> None:
        """
        Cache a finished pipeline result keyed by its source document hash.

        Re-uploading an identical document (common during demos and testing)
        then costs zero LLM requests instead of a full 7-call pipeline run.
        Callers must only cache successful runs - a cached "partial" would
        pin a transient LLM failure to that document until eviction.

        Args:
            document_hash: SHA-256 of the source PDF bytes or scanned text.
            payload:       Serialised PipelineResponse dict (route-level shape).
        """
        with self._result_lock:
            if len(self._result_by_hash) >= _PDF_STORE_MAX:
                self._result_by_hash.popitem(last=False)
            self._result_by_hash[document_hash] = payload

    def get_result_for_hash(self, document_hash: str) -> Optional[dict]:
        """
        Return the cached pipeline result for a document hash, or None.

        Args:
            document_hash: SHA-256 of the source PDF bytes or scanned text.

        Returns:
            dict | None: Cached PipelineResponse dict, or None if never
            cached or evicted.
        """
        with self._result_lock:
            return self._result_by_hash.get(document_hash)

    # ── Progress store ────────────────────────────────────────────────────────

    def set_progress(self, session_id: str, payload: dict) -> None:
        """
        Write a pipeline progress payload, stamping it with the current time.

        The timestamp is used by sweep_stale_progress() to evict entries that
        were never explicitly cleaned up (e.g. if the cleanup task was cancelled
        during server shutdown).

        Args:
            session_id: Session the progress event belongs to.
            payload:    Dict with status, current_agent, agent_name, message keys.
        """
        with self._progress_lock:
            self._progress[session_id] = {**payload, "created_at": time.time()}

    def get_progress(self, session_id: str) -> Optional[dict]:
        """
        Return the current progress payload for a session, or None.

        Args:
            session_id: Session to look up.

        Returns:
            dict | None: The last payload passed to set_progress(), plus the
            internal created_at timestamp, or None if no entry exists.
        """
        with self._progress_lock:
            return self._progress.get(session_id)

    def pop_progress(self, session_id: str) -> None:
        """
        Remove a progress entry (called after pipeline completes or errors).

        Args:
            session_id: Session whose progress entry should be removed.
        """
        with self._progress_lock:
            self._progress.pop(session_id, None)

    def sweep_stale_progress(self, now: Optional[float] = None) -> None:
        """
        Drop progress entries older than progress_ttl seconds.

        Called at the start of each GET /progress response to lazily evict
        entries from sessions whose cleanup tasks were cancelled (e.g. during
        server shutdown).

        Args:
            now: Reference timestamp. Uses time.time() when None.
        """
        if now is None:
            now = time.time()
        with self._progress_lock:
            stale = [
                sid
                for sid, p in self._progress.items()
                if now - p.get("created_at", now) > _PROGRESS_TTL_SECONDS
            ]
            for sid in stale:
                self._progress.pop(sid, None)


# Process-level singleton - one store per uvicorn worker.
# Routes import this directly; tests that need isolation should instantiate
# a fresh SessionStore() rather than mutating this singleton.
session_store = SessionStore()
