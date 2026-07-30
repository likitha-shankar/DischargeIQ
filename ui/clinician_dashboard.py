"""
File: ui/clinician_dashboard.py
Owner: Likitha Shankar
Description: Streamlit clinician dashboard (Sprint 3, Task 3.3) - a separate,
  clinician-facing surface (not a patient tab) showing anonymized session
  activity, per-session comprehension deltas from the teach-back quiz, and
  flagged knowledge gaps (domains patients still miss AFTER the learning
  cards). Reads Neon directly - point DATABASE_URL_RO at a read replica so
  analytics never touch transactional performance; falls back to DATABASE_URL.
Key functions/classes: main, _build_session_table (data layer + protocol
  math shared with evaluation/quiz_gap_report.py lives in ui/quiz_analytics.py)
Edge cases handled:
  - No DATABASE_URL configured → clear setup message, no stack trace.
  - Tables missing (fresh DB) → treated as zero rows, not an error.
  - Sessions with a quiz but no post phase (abandoned) → shown, delta blank.
Dependencies: streamlit, asyncpg, pandas (ships with streamlit), python-dotenv,
  ui.quiz_analytics (shared queries + miss-rate math).
Called by: `streamlit run ui/clinician_dashboard.py --server.port 8502`
  (self-contained on purpose - no dischargeiq imports, so it runs anywhere
  the two env vars reach the database).
"""

import asyncio
import json
import logging
import os
import random
from pathlib import Path

import asyncpg
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ui.quiz_analytics import DOMAIN_LABELS, domain_miss_rates, fetch_rows, quiz_by_session

load_dotenv(dotenv_path=".env")
logger = logging.getLogger(__name__)

# Comprehension-lift target band from the work plan (13% baseline -> 50-70%).
_TARGET_LOW, _TARGET_HIGH = 50, 70


@st.cache_data(ttl=60, show_spinner="Loading analytics…")
def _load_data(db_url: str) -> tuple[list[dict], list[dict]]:
    """
    Cached wrapper around fetch_rows, converted to plain dicts.

    Streamlit reruns the whole script on every interaction; the 60s TTL keeps
    replica load at ~1 query/minute regardless of clicking.

    Args:
        db_url: Postgres connection string (cache key).

    Returns:
        (history, quiz) as lists of plain dicts (asyncpg Records don't pickle
        for Streamlit's cache).
    """
    history, quiz = asyncio.run(fetch_rows(db_url))
    return [dict(r) for r in history], [dict(r) for r in quiz]


def _build_session_table(history: list[dict], quiz_sessions: dict[str, dict]) -> pd.DataFrame:
    """
    Join discharge sessions with their quiz outcomes into a display frame.

    Anonymization contract: only truncated random session ids and document
    hashes leave the database - discharge_history stores no patient names,
    and quiz_scores stores no question or answer text.

    Args:
        history: discharge_history rows (newest first).
        quiz_sessions: output of quiz_by_session.

    Returns:
        DataFrame with one row per analyzed document.
    """
    rows = []
    for h in history:
        q = quiz_sessions.get(h["session_id"], {})
        pre, post = q.get("pre"), q.get("post")
        delta = (post - pre) if (pre is not None and post is not None) else None
        rows.append(
            {
                "Session": h["session_id"][:8],
                "Document": (h["document_hash"] or "")[:8],
                "Diagnosis": h["primary_diagnosis"] or "-",
                "Pipeline": h["pipeline_status"] or "-",
                "Baseline %": pre,
                "Post %": post,
                "Lift (pts)": delta,
                "Analyzed": h["created_at"],
            }
        )
    return pd.DataFrame(rows)


def _render_metrics(df: pd.DataFrame, quiz_sessions: dict[str, dict]) -> None:
    """Render the headline stat tiles: volume, baseline, outcome, lift."""
    completed = [
        s for s in quiz_sessions.values() if s["pre"] is not None and s["post"] is not None
    ]
    avg_pre = sum(s["pre"] for s in completed) / len(completed) if completed else None
    avg_post = sum(s["post"] for s in completed) / len(completed) if completed else None
    avg_lift = (avg_post - avg_pre) if completed else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documents analyzed", len(df))
    c2.metric("Completed quiz loops", len(completed))
    c3.metric("Avg baseline", f"{avg_pre:.0f}%" if avg_pre is not None else "-")
    c4.metric(
        "Avg after teaching",
        f"{avg_post:.0f}%" if avg_post is not None else "-",
        delta=f"{avg_lift:+.0f} pts" if avg_lift is not None else None,
    )
    if avg_post is not None:
        on_target = _TARGET_LOW <= avg_post <= 100
        st.caption(
            f"Work-plan target: {_TARGET_LOW}–{_TARGET_HIGH}% comprehension after "
            f"teaching (from ~13% literature baseline). "
            + ("✅ On target." if on_target else "⚠️ Below target band.")
        )


def _render_flagged_gaps(quiz: list[dict]) -> None:
    """
    Render the flagged-gaps section: domains still missed AFTER teaching.

    A post-phase miss is the actionable signal for a care team - the app
    taught the topic and the patient still got it wrong.
    """
    st.subheader("Flagged knowledge gaps")
    post_miss = domain_miss_rates(quiz, "post")
    pre_miss = domain_miss_rates(quiz, "pre")
    if not pre_miss and not post_miss:
        st.info("No quiz data yet - gaps appear once patients take the teach-back quiz.")
        return

    flagged = {d: rate for d, rate in post_miss.items() if rate > 0}
    if flagged:
        worst = sorted(flagged.items(), key=lambda kv: kv[1], reverse=True)
        st.warning(
            "Still missed after teaching: "
            + ", ".join(f"**{d}** ({rate:.0%})" for d, rate in worst)
        )
    else:
        st.success("No domain is being missed after teaching.")

    # One axis, one comparison: miss rate per domain, before vs after teaching.
    domains = sorted(set(pre_miss) | set(post_miss))
    chart_df = pd.DataFrame(
        {
            "Missed at baseline": [pre_miss.get(d, 0.0) for d in domains],
            "Missed after teaching": [post_miss.get(d, 0.0) for d in domains],
        },
        index=domains,
    )
    st.bar_chart(chart_df, horizontal=True)
    st.caption("Fraction of quiz questions missed per domain, across all sessions.")


def _render_spot_check() -> None:
    """
    Random-sample review queue (Task 2.4) - the human-in-the-loop check from
    the July review: a clinician is served a random document's generated
    outputs to verify against the source, instead of choosing what to read.

    Reads the frozen review set on disk (evaluation/corpus_outputs/, written
    by scripts/run_corpus_for_review.py). Deliberately NOT the live database:
    agent free-text is never stored in Neon (privacy rule), so disk outputs
    generated from the synthetic corpus are the only reviewable artifacts.
    """
    st.subheader("Spot-check a random document")
    outputs = sorted(Path("evaluation/corpus_outputs").glob("*.json"))
    if not outputs:
        st.info(
            "No generated outputs to review yet. Run "
            "`python scripts/run_corpus_for_review.py` once to build the "
            "frozen review set from the synthetic corpus."
        )
        return

    # The current pick lives in session state so Streamlit reruns (any widget
    # interaction) do not silently swap the document mid-review.
    if st.button("🎲 Serve me a random document") or "spot_check_pick" not in st.session_state:
        st.session_state["spot_check_pick"] = random.choice(outputs).name
    pick = Path("evaluation/corpus_outputs") / st.session_state["spot_check_pick"]
    if not pick.is_file():  # set regenerated since last visit
        st.session_state["spot_check_pick"] = random.choice(outputs).name
        pick = Path("evaluation/corpus_outputs") / st.session_state["spot_check_pick"]

    try:
        payload = json.loads(pick.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        st.error(f"Could not read {pick.name}: {exc}")
        return

    extraction = payload.get("extraction") or {}
    st.markdown(
        f"**Document:** `{pick.stem}`  ·  status `{payload.get('pipeline_status', '?')}`  ·  "
        f"extracted diagnosis: *{extraction.get('primary_diagnosis', 'n/a')}*"
    )
    st.caption(
        "Verify against the matching source PDF in test-data/. "
        "Checklist: summary matches the source; every medication, dose, and "
        "frequency exact; warning signs complete and unambiguous; nothing "
        "added that is not in the source. Score it in the review portal "
        "(port 8503) when done."
    )
    sections = [
        ("What happened (Agent 2)", payload.get("diagnosis_explanation", "")),
        ("Medications (Agent 3)", payload.get("medication_rationale", "")),
        ("Recovery (Agent 4)", payload.get("recovery_trajectory", "")),
        ("Warning signs (Agent 5)", payload.get("escalation_guide", "")),
    ]
    for title, text in sections:
        with st.expander(title, expanded=False):
            st.markdown(text if text.strip() else "*empty - agent failed on this run*")
    meds = extraction.get("medications") or []
    if meds:
        with st.expander(f"Extracted medications ({len(meds)}) - verify doses", expanded=False):
            st.dataframe(pd.DataFrame(meds), hide_index=True, width="stretch")


def main() -> None:
    """Page entry point: config check, data load, metrics, gaps, session table."""
    st.set_page_config(page_title="DischargeIQ - Clinician Dashboard", page_icon="🩺", layout="wide")
    st.title("🩺 Clinician Dashboard")
    st.caption(
        "Anonymized teach-back analytics. Sessions are random ids - no names, "
        "no document text, no quiz answer text is ever stored. Gaps flagged "
        "here are discussion prompts for the care team, not diagnoses."
    )

    db_url = os.getenv("DATABASE_URL_RO") or os.getenv("DATABASE_URL")
    if not db_url:
        st.error(
            "No database configured. Set `DATABASE_URL_RO` (Neon read replica, "
            "preferred for analytics) or `DATABASE_URL` in `.env`."
        )
        return
    if not os.getenv("DATABASE_URL_RO"):
        st.caption("ℹ️ Using the primary DATABASE_URL - set DATABASE_URL_RO to a read replica in production.")

    try:
        history, quiz = _load_data(db_url)
    except (asyncpg.PostgresError, OSError) as exc:
        logger.error("dashboard DB load failed: %s", exc)
        st.error(f"Could not reach the database: {exc}")
        return

    quiz_sessions = quiz_by_session(quiz)
    df = _build_session_table(history, quiz_sessions)

    _render_metrics(df, quiz_sessions)
    st.divider()
    _render_flagged_gaps(quiz)
    st.divider()
    _render_spot_check()
    st.divider()

    st.subheader("Sessions")
    if df.empty:
        st.info("No analyzed documents yet.")
    else:
        st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            column_config={
                "Baseline %": st.column_config.NumberColumn(format="%.0f%%"),
                "Post %": st.column_config.NumberColumn(format="%.0f%%"),
                "Lift (pts)": st.column_config.NumberColumn(format="%+.0f"),
                "Analyzed": st.column_config.DatetimeColumn(format="MMM D, HH:mm"),
            },
        )
    st.button("Refresh", on_click=_load_data.clear)


main()
