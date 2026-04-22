"""
Database access layer for discharge history (Neon PostgreSQL).

Provides functions to save and retrieve pipeline results. Only structured
fields, hashes, and metadata are stored — never full PDF text or free-text
agent outputs.

Depends on: asyncpg, dischargeiq.models.extraction.
"""

# READ PATH — not yet implemented.
# get_history_for_session() is defined below but not called
# anywhere in the current UI. When the patient history screen
# is built, wire it up in main.py as:
#   GET /history/{session_id} -> get_history_for_session()
# and add a "Past summaries" tab to streamlit_app.py.

import json
import logging

import asyncpg

from dischargeiq.models.extraction import ExtractionOutput

logger = logging.getLogger(__name__)


async def get_db_pool(database_url: str) -> asyncpg.Pool:
    """
    Create and return an asyncpg connection pool.

    Args:
        database_url: Neon PostgreSQL connection string from DATABASE_URL env var.

    Returns:
        asyncpg.Pool: A connection pool with 1–5 connections.

    Raises:
        asyncpg.PostgresError: If the database is unreachable or credentials are wrong.
    """
    try:
        pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
        logger.info("Database connection pool created successfully.")
        return pool
    except asyncpg.PostgresError as db_error:
        logger.error("Failed to create database pool: %s", db_error)
        raise


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
        pipeline_status: "complete" or "partial".

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
                json.dumps(extraction.model_dump()),
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
