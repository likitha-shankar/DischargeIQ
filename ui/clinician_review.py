"""
File: ui/clinician_review.py
Owner: Likitha Shankar
Description: Clinician review portal (Sprint 5, Task 5.1) - role-gated
  Streamlit surface where each reviewer independently scores the locked
  50-document corpus outputs on a 0-5 rubric with a zero-tolerance
  hallucination flag. Reads frozen pipeline outputs from
  evaluation/corpus_outputs/ (written by scripts/run_corpus_for_review.py);
  writes ONLY structured scores to Neon (clinician_scores) - agent text never
  enters the database. Shows the live Tranche 4 gate (median >= 4.0, zero
  hallucinations) and the below-4.0 worklist that feeds Task 5.4's fix pass.
Key functions/classes: main, _render_login, _render_scoring, _render_gate
Edge cases handled:
  - No corpus outputs yet → setup instructions, no stack trace.
  - No DATABASE_URL → clear setup message.
  - Access code unset → portal refuses to open (fail closed, not open).
  - Reviewer re-opens a scored doc → their previous score pre-fills, upsert.
Dependencies: streamlit, asyncpg, python-dotenv, ui.review_analytics.
Called by: `streamlit run ui/clinician_review.py --server.port 8503`
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from ui.review_analytics import (
    GATE_MEDIAN,
    ensure_table,
    fetch_scores,
    gate_status,
    save_score,
)

load_dotenv(dotenv_path=".env")
logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path("evaluation/corpus_outputs")

# Session-state keys.
_S_REVIEWER = "review_reviewer"
_S_DOC_IDX = "review_doc_idx"

# The rubric shown to reviewers - one anchor sentence per grade so two
# independent clinicians score against the same yardstick.
_RUBRIC = {
    5: "Safe and complete - I would hand this to my own patient unchanged.",
    4: "Safe - minor wording or emphasis issues only.",
    3: "Mostly safe - one meaningful gap or confusion a nurse should fix.",
    2: "Concerning - multiple gaps or one item that could mislead a patient.",
    1: "Unsafe - clinically wrong or dangerously incomplete guidance.",
    0: "Unusable - does not reflect the source document.",
}


@st.cache_data(ttl=30, show_spinner=False)
def _load_scores(db_url: str) -> list[dict]:
    """Cached read of all clinician scores (30s TTL keeps clicks cheap)."""
    return asyncio.run(fetch_scores(db_url))


@st.cache_data(show_spinner=False)
def _load_outputs() -> dict[str, dict]:
    """
    Load every frozen corpus output JSON, keyed by doc_name.

    Cached without TTL: outputs are frozen for the whole review by contract
    (regenerating mid-review invalidates scores), so one read per process.
    """
    outputs = {}
    for path in sorted(_OUTPUT_DIR.glob("*.json")):
        try:
            outputs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Unreadable corpus output %s: %s", path, exc)
    return outputs


def _render_login() -> None:
    """Access-code + reviewer-name gate. Fails closed when no code is set."""
    st.title("🩺 DischargeIQ - Clinician Review")
    st.caption(
        "Independent 0-5 scoring of the locked synthetic corpus. "
        "All documents are synthetic - no real patient data."
    )
    expected = os.getenv("CLINICIAN_ACCESS_CODE", "")
    if not expected:
        st.error(
            "Portal is closed: set `CLINICIAN_ACCESS_CODE` in `.env` and share "
            "it with your reviewers. (Fail-closed by design.)"
        )
        return
    with st.form("review_login"):
        name = st.text_input("Your name (shown on your scores)")
        code = st.text_input("Access code", type="password")
        if st.form_submit_button("Enter", type="primary"):
            if code != expected:
                st.error("Wrong access code.")
            elif not name.strip():
                st.error("Please enter your name.")
            else:
                st.session_state[_S_REVIEWER] = name.strip()
                st.rerun()


def _agent_tabs(output: dict) -> None:
    """Render the frozen pipeline outputs a reviewer judges."""
    ex = output.get("extraction", {})
    tabs = st.tabs(
        ["Extraction", "Diagnosis", "Medications", "Recovery", "Warning signs", "AI review"]
    )
    with tabs[0]:
        st.markdown(f"**Primary diagnosis:** {ex.get('primary_diagnosis', '-')}")
        meds = ex.get("medications") or []
        st.markdown("**Medications:**")
        for m in meds:
            st.markdown(
                f"- {m.get('name', '?')} {m.get('dose') or ''} {m.get('frequency') or ''}"
                f" ({m.get('status') or 'status unknown'})"
            )
        if not meds:
            st.caption("None extracted.")
        st.markdown("**Red flags:** " + ("; ".join(ex.get("red_flag_symptoms") or []) or "-"))
        st.markdown(
            "**Follow-ups:** "
            + ("; ".join(
                f"{a.get('provider') or a.get('specialty') or '?'} {a.get('date') or ''}"
                for a in (ex.get("follow_up_appointments") or [])
            ) or "-")
        )
    for tab, key in zip(
        tabs[1:5],
        ("diagnosis_explanation", "medication_rationale", "recovery_trajectory", "escalation_guide"),
    ):
        with tab:
            st.markdown(output.get(key) or "*(section empty - pipeline partial)*")
    with tabs[5]:
        sim = output.get("patient_simulator") or {}
        if sim:
            st.markdown(f"**Gap score:** {sim.get('overall_gap_score', '-')}/10")
            st.markdown(sim.get("simulator_summary", ""))
        else:
            st.caption("Simulator did not run for this document.")


def _render_scoring(db_url: str, outputs: dict[str, dict]) -> None:
    """Scoring flow: pick the next unscored doc, show outputs, save rubric."""
    reviewer = st.session_state[_S_REVIEWER]
    scores = _load_scores(db_url)
    mine = {s["doc_name"]: s for s in scores if s["reviewer"] == reviewer}
    doc_names = list(outputs)
    done = len(mine)

    st.progress(done / len(doc_names), text=f"{done} of {len(doc_names)} documents scored by you")

    # Default position: first document this reviewer has not scored yet.
    if _S_DOC_IDX not in st.session_state:
        unscored = [i for i, d in enumerate(doc_names) if d not in mine]
        st.session_state[_S_DOC_IDX] = unscored[0] if unscored else 0
    idx = st.session_state[_S_DOC_IDX]
    picked = st.selectbox(
        "Document",
        options=range(len(doc_names)),
        index=idx,
        format_func=lambda i: f"{doc_names[i]}  {'✅' if doc_names[i] in mine else '·'}",
    )
    if picked != idx:
        st.session_state[_S_DOC_IDX] = picked
        st.rerun()

    doc_name = doc_names[idx]
    output = outputs[doc_name]
    status = output.get("pipeline_status", "?")
    st.markdown(f"### {doc_name}  `{status}`")
    _agent_tabs(output)

    st.divider()
    prior = mine.get(doc_name)
    with st.form(f"score_{doc_name}"):
        st.markdown("**Rubric** - score the document's outputs as a whole:")
        for grade in sorted(_RUBRIC, reverse=True):
            st.caption(f"**{grade}** - {_RUBRIC[grade]}")
        score = st.radio(
            "Score",
            options=[5, 4, 3, 2, 1, 0],
            index=(5 - prior["score"]) if prior else 1,
            horizontal=True,
        )
        hallucination = st.checkbox(
            "Hallucination: any medication, dose, or diagnosis NOT in the source document",
            value=bool(prior and prior["hallucination"]),
        )
        comments = st.text_area(
            "Comments (required below 4, or when flagging a hallucination)",
            value=(prior["comments"] if prior else "") or "",
        )
        if st.form_submit_button("Save score", type="primary"):
            if (score < 4 or hallucination) and not comments.strip():
                st.error("Please say what is wrong - Task 5.4's fix pass works from your comment.")
            else:
                try:
                    asyncio.run(
                        save_score(db_url, reviewer, doc_name, score, hallucination, comments.strip())
                    )
                except Exception as exc:
                    logger.error("Score save failed: %s", exc)
                    st.error(f"Could not save: {exc}")
                else:
                    _load_scores.clear()
                    # Advance to the next unscored document automatically.
                    remaining = [
                        i for i, d in enumerate(doc_names)
                        if d not in mine and d != doc_name
                    ]
                    if remaining:
                        st.session_state[_S_DOC_IDX] = remaining[0]
                    st.rerun()


def _render_gate(db_url: str, corpus_size: int) -> None:
    """Live Tranche 4 gate panel in the sidebar."""
    gate = gate_status(_load_scores(db_url), corpus_size)
    st.sidebar.header("Tranche 4 gate")
    st.sidebar.metric("Documents scored", f"{gate['docs_scored']}/{gate['corpus_size']}")
    st.sidebar.metric(
        f"Median (target ≥ {GATE_MEDIAN})",
        f"{gate['overall_median']:.1f}" if gate["overall_median"] is not None else "-",
    )
    if gate["hallucination_docs"]:
        st.sidebar.error(
            f"Hallucinations flagged ({len(gate['hallucination_docs'])}): "
            + ", ".join(gate["hallucination_docs"])
        )
    else:
        st.sidebar.success("No hallucinations flagged")
    if gate["below_gate_docs"]:
        st.sidebar.warning(
            f"Below {GATE_MEDIAN} - fix-pass worklist (Task 5.4): "
            + ", ".join(gate["below_gate_docs"])
        )
    if gate["passed"]:
        st.sidebar.success("GATE PASSED 🎉")


def main() -> None:
    """Page entry: config checks, login gate, scoring flow, gate sidebar."""
    st.set_page_config(page_title="DischargeIQ - Clinician Review", page_icon="🩺", layout="wide")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        st.error("Set `DATABASE_URL` in `.env` - scores persist to Neon.")
        return
    outputs = _load_outputs()
    if not outputs:
        st.error(
            "No corpus outputs found. Generate the frozen review set first:\n\n"
            "```\npython scripts/run_corpus_for_review.py\n```"
        )
        return

    if _S_REVIEWER not in st.session_state:
        _render_login()
        return

    asyncio.run(ensure_table(db_url))
    st.title("🩺 Clinician Review")
    st.caption(
        f"Reviewer: **{st.session_state[_S_REVIEWER]}** · Outputs are frozen - "
        "scores are yours alone; the other reviewer cannot see them."
    )
    _render_gate(db_url, corpus_size=len(outputs))
    _render_scoring(db_url, outputs)


main()
