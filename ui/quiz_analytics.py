"""
File: ui/quiz_analytics.py
Owner: Likitha Shankar
Description: Shared quiz-analytics data layer (Sprint 3, Tasks 3.3/3.4) -
  Neon reads plus the baseline/post protocol math used by BOTH the clinician
  dashboard and the prompt-tuning gap report. Lives outside any Streamlit
  module on purpose: importing it never touches streamlit, so CLI scripts
  stay quiet and testable.
Key functions/classes: fetch_rows, quiz_by_session, domain_miss_rates, DOMAIN_LABELS
Edge cases handled:
  - Missing tables (fresh DB) → empty lists, never an error.
  - domain_scores arriving as JSON strings (asyncpg JSONB default) or dicts.
Dependencies: asyncpg.
Called by: ui/clinician_dashboard.py, evaluation/quiz_gap_report.py.
"""

import json
import logging

import asyncpg

logger = logging.getLogger(__name__)

# Patient-facing labels for the five quiz domains (mirrors ui/quiz_tab.py).
DOMAIN_LABELS = {
    "diagnosis": "What happened",
    "medications": "Medications",
    "follow_up": "Follow-up visits",
    "activity": "Activity & diet",
    "red_flags": "Warning signs",
}


async def fetch_rows(db_url: str) -> tuple[list, list]:
    """
    Fetch discharge sessions and quiz scores in one short-lived connection.

    A single one-shot connection (not a pool) is deliberate: analytics reads
    are low-traffic and callers cache, so pooling adds state for no benefit.

    Args:
        db_url: Postgres connection string (read replica preferred).

    Returns:
        (history_rows, quiz_rows) as lists of asyncpg Records. A missing
        table (fresh database) yields an empty list for that side.

    Raises:
        asyncpg.PostgresError: On connection/auth failures (caller handles).
    """
    conn = await asyncpg.connect(db_url)
    try:
        async def _safe(query: str) -> list:
            # Fresh deployments create tables lazily on first write, so a
            # missing table just means "no data yet" - never an error page.
            try:
                return await conn.fetch(query)
            except asyncpg.UndefinedTableError:
                return []

        history = await _safe(
            """
            SELECT session_id, document_hash, primary_diagnosis,
                   pipeline_status, created_at
            FROM discharge_history
            ORDER BY created_at DESC
            LIMIT 500
            """
        )
        quiz = await _safe(
            """
            SELECT session_id, phase, percent, domain_scores, created_at
            FROM quiz_scores
            ORDER BY created_at ASC
            LIMIT 5000
            """
        )
        return history, quiz
    finally:
        await conn.close()


def _parse_domains(raw) -> dict | None:
    """Normalize a domain_scores column value (JSONB str or dict) to a dict."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("unparseable domain_scores value")
            return None
    return raw


def quiz_by_session(quiz: list[dict]) -> dict[str, dict]:
    """
    Reduce quiz rows to one record per session: honest baseline + final post.

    Protocol match with dischargeiq/db/quiz.py: the FIRST pre row is the
    baseline (retakes are inflated by exposure); the LAST post row is the
    outcome (mastery-path retakes count - they reflect what the patient
    finally knows).

    Args:
        quiz: quiz_scores rows sorted ascending by created_at.

    Returns:
        {session_id: {"pre": float|None, "post": float|None,
                      "post_domains": dict|None}}
    """
    sessions: dict[str, dict] = {}
    for row in quiz:
        entry = sessions.setdefault(
            row["session_id"], {"pre": None, "post": None, "post_domains": None}
        )
        if row["phase"] == "pre" and entry["pre"] is None:
            entry["pre"] = float(row["percent"])
        elif row["phase"] == "post":
            entry["post"] = float(row["percent"])
            entry["post_domains"] = _parse_domains(row["domain_scores"])
    return sessions


def domain_miss_rates(quiz: list[dict], phase: str) -> dict[str, float]:
    """
    Aggregate miss rate per quiz domain across all sessions for one phase.

    Args:
        quiz: quiz_scores rows.
        phase: "pre" (baseline gaps) or "post" (persistent, flagged gaps).

    Returns:
        {domain_label: missed_fraction 0..1} for domains with any data.
    """
    missed: dict[str, int] = {}
    total: dict[str, int] = {}
    for row in quiz:
        if row["phase"] != phase:
            continue
        domains = _parse_domains(row["domain_scores"])
        for domain, counts in (domains or {}).items():
            label = DOMAIN_LABELS.get(domain, domain)
            total[label] = total.get(label, 0) + counts.get("total", 0)
            missed[label] = missed.get(label, 0) + (
                counts.get("total", 0) - counts.get("correct", 0)
            )
    return {d: missed[d] / total[d] for d in total if total[d] > 0}
