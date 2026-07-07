"""
File: ui/review_analytics.py
Owner: Likitha Shankar
Description: Data layer + gate math for the clinician review portal (Sprint 5,
  Task 5.1). Owns the clinician_scores table (DDL, insert, fetch) and the
  Tranche 4 acceptance-gate computation: median score >= 4.0 across the locked
  corpus with zero hallucination flags. Streamlit-free on purpose (same pattern
  as quiz_analytics.py) so the gate math is unit-testable and reusable by the
  final Tranche 4 report script.
Key functions/classes: ensure_table, save_score, fetch_scores, doc_rollup,
  gate_status
Edge cases handled:
  - Missing table (fresh DB) → fetch returns [], never an error.
  - A reviewer re-scoring a document updates their previous row (one score
    per reviewer per document, enforced by a unique constraint).
Dependencies: asyncpg.
Called by: ui/clinician_review.py; later the Tranche 4 summary report.
"""

import logging
from statistics import median

import asyncpg

logger = logging.getLogger(__name__)

# Tranche 4 acceptance gate (docs/deliverables/tranche-4-clinical-validation.md).
GATE_MEDIAN = 4.0

# One row per (reviewer, document). Re-scoring updates in place - a reviewer's
# latest judgment is the one that counts; there is no score history by design.
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS clinician_scores (
    id SERIAL PRIMARY KEY,
    reviewer VARCHAR(120) NOT NULL,
    doc_name VARCHAR(64) NOT NULL,
    score SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 5),
    hallucination BOOLEAN NOT NULL DEFAULT FALSE,
    comments TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (reviewer, doc_name)
);
"""

_UPSERT_SQL = """
INSERT INTO clinician_scores (reviewer, doc_name, score, hallucination, comments)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (reviewer, doc_name) DO UPDATE SET
    score = EXCLUDED.score,
    hallucination = EXCLUDED.hallucination,
    comments = EXCLUDED.comments,
    created_at = NOW();
"""


async def ensure_table(db_url: str) -> None:
    """Create clinician_scores if it does not exist (idempotent)."""
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(_CREATE_TABLE_SQL)
    finally:
        await conn.close()


async def save_score(
    db_url: str,
    reviewer: str,
    doc_name: str,
    score: int,
    hallucination: bool,
    comments: str,
) -> None:
    """
    Upsert one rubric score. Only structured fields are stored - the agent
    text being judged lives in evaluation/corpus_outputs/, never in Neon.

    Raises:
        asyncpg.PostgresError: On connection or constraint failure - the
            portal surfaces this to the reviewer rather than losing the score
            silently.
    """
    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute(_UPSERT_SQL, reviewer, doc_name, score, hallucination, comments)
    finally:
        await conn.close()


async def fetch_scores(db_url: str) -> list[dict]:
    """
    All clinician scores, as plain dicts (safe for Streamlit caching).

    Returns [] when the table does not exist yet (fresh database) so the
    portal renders its empty state instead of a stack trace.
    """
    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch(
            "SELECT reviewer, doc_name, score, hallucination, comments, created_at"
            " FROM clinician_scores ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]
    except asyncpg.UndefinedTableError:
        return []
    finally:
        await conn.close()


def doc_rollup(scores: list[dict]) -> dict[str, dict]:
    """
    Aggregate scores per document.

    Args:
        scores: clinician_scores rows (any order).

    Returns:
        {doc_name: {"scores": [int], "reviewers": [str], "median": float,
                    "hallucination": bool}} - hallucination is True if ANY
        reviewer flagged one (the gate is zero tolerance, so one flag taints
        the document).
    """
    rollup: dict[str, dict] = {}
    for row in scores:
        entry = rollup.setdefault(
            row["doc_name"],
            {"scores": [], "reviewers": [], "median": 0.0, "hallucination": False},
        )
        entry["scores"].append(row["score"])
        entry["reviewers"].append(row["reviewer"])
        entry["hallucination"] = entry["hallucination"] or bool(row["hallucination"])
    for entry in rollup.values():
        entry["median"] = float(median(entry["scores"]))
    return rollup


def gate_status(scores: list[dict], corpus_size: int) -> dict:
    """
    Compute the Tranche 4 acceptance gate over the current scores.

    The gate (work plan): median >= 4.0 over the corpus AND zero
    medication/diagnostic hallucinations. The overall median is taken over
    per-document medians so a document double-scored by both reviewers does
    not weigh twice against a single-scored one.

    Args:
        scores: clinician_scores rows.
        corpus_size: Number of documents in the locked corpus (usually 50).

    Returns:
        dict with keys: docs_scored, corpus_size, overall_median (None until
        any score exists), hallucination_docs (list of tainted doc names),
        below_gate_docs (list of docs with median < GATE_MEDIAN - the Task
        5.4 fix-pass worklist), passed (bool - only meaningful when
        docs_scored == corpus_size).
    """
    rollup = doc_rollup(scores)
    doc_medians = [e["median"] for e in rollup.values()]
    hallucination_docs = sorted(d for d, e in rollup.items() if e["hallucination"])
    below_gate = sorted(d for d, e in rollup.items() if e["median"] < GATE_MEDIAN)
    overall = float(median(doc_medians)) if doc_medians else None
    return {
        "docs_scored": len(rollup),
        "corpus_size": corpus_size,
        "overall_median": overall,
        "hallucination_docs": hallucination_docs,
        "below_gate_docs": below_gate,
        "passed": (
            len(rollup) == corpus_size
            and overall is not None
            and overall >= GATE_MEDIAN
            and not hallucination_docs
        ),
    }
