"""
File: dischargeiq/db/quiz.py
Owner: Likitha Shankar
Description: Async Neon helpers for teach-back quiz scores (Sprint 3, Task 3.1) -
  table creation, per-phase score inserts, and pre-score lookup for the
  comprehension delta. All failures are logged and non-fatal: the quiz works
  without a database, it just doesn't accumulate lift data.
Key functions/classes: save_quiz_score, get_latest_pre_percent
Edge cases handled:
  - pool=None (DATABASE_URL unset) → both functions no-op with a debug log.
  - Only structured fields stored - no question text, no raw answers content.
Dependencies: asyncpg, dischargeiq.models.quiz.QuizScoreResult
Called by: dischargeiq.api.routes.quiz
"""

import json
import logging

import asyncpg

from dischargeiq.models.quiz import QuizScoreResult

logger = logging.getLogger(__name__)

# Structured scores only - never question text or free-text answers.
# session_id + phase is intentionally NOT unique: a mastery-path retake adds a
# new row, and analysis takes the latest (or first, for the honest baseline).
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS quiz_scores (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    phase VARCHAR(4) NOT NULL,
    score INT NOT NULL,
    total INT NOT NULL,
    percent REAL NOT NULL,
    domain_scores JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quiz_scores_session ON quiz_scores (session_id, phase);
"""

_table_ready = False


async def _ensure_table(pool: asyncpg.Pool) -> None:
    """Create the quiz_scores table on first use (idempotent, once per process)."""
    global _table_ready
    if _table_ready:
        return
    async with pool.acquire() as conn:
        await conn.execute(_CREATE_TABLE_SQL)
    _table_ready = True


async def save_quiz_score(pool: asyncpg.Pool | None, result: QuizScoreResult) -> None:
    """
    Persist one quiz phase score. Non-fatal on any failure.

    Args:
        pool: App DB pool, or None when DATABASE_URL is unset.
        result: The computed score for this phase.
    """
    if pool is None:
        logger.debug("quiz_scores: no DB pool - score not persisted")
        return
    try:
        await _ensure_table(pool)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO quiz_scores (session_id, phase, score, total, percent, domain_scores)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                result.session_id,
                result.phase,
                result.score,
                result.total,
                result.percent,
                json.dumps(result.domain_scores),
            )
    except asyncpg.PostgresError as exc:
        logger.warning("quiz_scores insert failed (non-fatal): %s", exc)


async def get_latest_pre_percent(pool: asyncpg.Pool | None, session_id: str) -> float | None:
    """
    Return the FIRST recorded pre-phase percent for a session, or None.

    The first pre score is the honest baseline - later retakes of the baseline
    (if any) are inflated by exposure and must not shrink the measured lift.

    Args:
        pool: App DB pool, or None when DATABASE_URL is unset.
        session_id: The quiz session to look up.
    """
    if pool is None:
        return None
    try:
        await _ensure_table(pool)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT percent FROM quiz_scores
                WHERE session_id = $1 AND phase = 'pre'
                ORDER BY created_at ASC LIMIT 1
                """,
                session_id,
            )
        return float(row["percent"]) if row else None
    except asyncpg.PostgresError as exc:
        logger.warning("quiz_scores pre lookup failed (non-fatal): %s", exc)
        return None
