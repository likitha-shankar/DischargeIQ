"""
File: dischargeiq/db/history.py
Owner: Likitha Shankar
Description: Async PostgreSQL helpers (asyncpg) for Neon - connection pool creation,
  insert of discharge_history rows (structured extraction JSON + fk_scores + status),
  and session lookup placeholder; DB failures are logged but should not crash analysis.
Key functions/classes: get_db_pool, save_discharge_history, get_history_for_session
Edge cases handled:
  - Read API noted as not wired in UI yet; callers must pass valid DATABASE_URL.
Dependencies: asyncpg, dischargeiq.models.extraction.ExtractionOutput
Called by: dischargeiq.pipeline.orchestrator (_save_history_with_retries), dischargeiq.main
  (pool for /health DB check when configured).
"""

# READ PATH - not yet implemented.
# get_history_for_session() is defined below but not called
# anywhere in the current UI. When the patient history screen
# is built, wire it up in main.py as:
#   GET /history/{session_id} -> get_history_for_session()
# and add a "Past summaries" tab to streamlit_app.py.

import asyncio
import json
import logging

import asyncpg

from dischargeiq.models.extraction import ExtractionOutput

logger = logging.getLogger(__name__)


# Neon suspends an idle database on the free tier and takes several seconds to
# wake. Cloud Run also scales to zero, so a cold container regularly races a
# sleeping database and loses. Retrying turns that race into a delay.
_POOL_ATTEMPTS = 4
_POOL_BASE_DELAY_SECONDS = 1.5


async def get_db_pool(
    database_url: str,
    attempts: int = _POOL_ATTEMPTS,
    base_delay: float = _POOL_BASE_DELAY_SECONDS,
) -> asyncpg.Pool:
    """
    Create and return an asyncpg connection pool, retrying a cold database.

    Args:
        database_url: Neon PostgreSQL connection string from DATABASE_URL.
        attempts: Total tries before giving up.
        base_delay: Seconds before the first retry; doubles each time.

    Returns:
        asyncpg.Pool: A connection pool with 1-5 connections.

    Raises:
        Exception: The last failure, when every attempt is exhausted.

    Note:
        Catches Exception rather than asyncpg.PostgresError on purpose. The
        failure seen in production on 12, 19 and 25 Aug 2026 was
        "Authentication timed out", which is a timeout and NOT a PostgresError,
        so the previous narrower except never ran and the error escaped to a
        caller that swallowed it. Losing the database is silent by design here
        (analysis must still work), which is exactly why the retry has to
        happen at this level.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
            if attempt > 1:
                logger.info(
                    "Database connection pool created on attempt %d.", attempt
                )
            else:
                logger.info("Database connection pool created successfully.")
            return pool
        except Exception as db_error:  # noqa: BLE001 - see the note above
            last_error = db_error
            if attempt == attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "DB pool attempt %d/%d failed (%s); retrying in %.1fs",
                attempt, attempts, db_error, delay,
            )
            await asyncio.sleep(delay)

    logger.error(
        "Failed to create database pool after %d attempts: %s", attempts, last_error
    )
    raise last_error if last_error else RuntimeError("pool creation failed")



#: Extraction fields that must never reach the database.
#:
#: `patient_name` is a direct identifier - one of the eighteen under HIPAA -
#: and every `*_source` span carries VERBATIM text lifted out of the document,
#: which can contain anything the hospital wrote there: names, dates of birth,
#: record numbers, addresses.
#:
#: CLAUDE.md has always said "never store full PDF text or free-text agent
#: outputs in the database; only structured fields, hashes, and metadata". The
#: insert wrote `extraction.model_dump()` whole, which satisfies "structured
#: fields" on a literal reading and defeats the intent: 272 verbatim source
#: spans across the 106-document corpus, plus a name column.
#:
#: This is invisible on the current corpus - MTSamples is de-identified, so
#: `patient_name` extracts as "female" or "The patient". On real paperwork it
#: is a real name, and the store becomes a HIPAA record with no retention
#: policy and no deletion path.
_NEVER_PERSIST = frozenset({"patient_name"})


def redact_for_storage(extraction: ExtractionOutput) -> dict:
    """
    Strip direct identifiers and verbatim source text before persisting.

    Args:
        extraction: Validated Agent 1 output.

    Returns:
        dict: The extraction with `patient_name` and every `*_source` span
        removed. Clinical structure - diagnoses, medications, appointments,
        restrictions, warning signs - is kept, because that is what the
        history screen and the clinician dashboard exist to show.

    Note:
        Provenance spans are dropped from STORAGE only. They still travel in
        the live API response, where the app draws citation chips from them,
        and they are still what makes an extracted value traceable. They are
        simply not worth keeping at rest.
    """
    payload = extraction.model_dump()
    return {
        key: value
        for key, value in payload.items()
        if key not in _NEVER_PERSIST and not key.endswith("_source")
    }


async def save_discharge_history(
    pool: asyncpg.Pool,
    session_id: str,
    document_hash: str,
    extraction: ExtractionOutput,
    fk_scores: dict,
    pipeline_status: str,
) -> int:
    """
    Insert a completed pipeline result into discharge_history.

    Args:
        pool: Active asyncpg connection pool.
        session_id: Unique session identifier for the user.
        document_hash: SHA-256 hash of the uploaded PDF for deduplication.
        extraction: Validated Agent 1 output.
        fk_scores: Flesch-Kincaid scores for each agent's text output.
        pipeline_status: "complete", "complete_with_warnings", or "partial".

    Returns:
        int: The auto-generated row id of the inserted record.

    Raises:
        asyncpg.PostgresError: If the insert fails.
    """
    try:
        async with pool.acquire() as conn:
            row_id = await conn.fetchval(
                """
                INSERT INTO discharge_history
                    (session_id, document_hash, primary_diagnosis, discharge_date,
                     pipeline_status, extracted_fields, fk_scores)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
                RETURNING id
                """,
                session_id,
                document_hash,
                extraction.primary_diagnosis,
                extraction.discharge_date,
                pipeline_status,
                json.dumps(redact_for_storage(extraction)),
                json.dumps(fk_scores),
            )
        logger.info("Saved discharge history row %d for session %s", row_id, session_id)
        return row_id
    except asyncpg.PostgresError as db_error:
        logger.error("Failed to save discharge history: %s", db_error)
        raise


async def get_history_for_session(
    pool: asyncpg.Pool,
    session_id: str,
) -> list[dict]:
    """
    Retrieve all discharge history records for a given session.

    Args:
        pool: Active asyncpg connection pool.
        session_id: The session to look up.

    Returns:
        list[dict]: Rows ordered by created_at descending. Empty list if none found.

    Raises:
        asyncpg.PostgresError: If the query fails.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, session_id, document_hash, primary_diagnosis,
                       discharge_date, pipeline_status, extracted_fields,
                       fk_scores, created_at
                FROM discharge_history
                WHERE session_id = $1
                ORDER BY created_at DESC
                """,
                session_id,
            )
        return [dict(row) for row in rows]
    except asyncpg.PostgresError as db_error:
        logger.error("Failed to fetch history for session %s: %s", session_id, db_error)
        raise
