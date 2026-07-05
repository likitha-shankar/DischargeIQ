"""
File: ui/quiz_tab.py
Owner: Likitha Shankar
Description: "Test yourself" tab for the Streamlit fallback surface (Sprint 3,
  Task 3.2) - the same teach-back loop as the mobile app: baseline quiz (no
  feedback) → learning cards → post-quiz (feedback + explanations) → results
  with the comprehension lift. Mirrors the mobile flow so demos are equivalent
  on either surface; the phone app remains the primary product.
Key functions/classes: render_quiz_tab
Edge cases handled:
  - /quiz/generate failure → friendly retry, never a stack trace.
  - /quiz/score failure → local scoring fallback so the flow never dead-ends.
Dependencies: streamlit, requests. Talks to POST /quiz/generate, /quiz/score.
Called by: streamlit_app.py (_SECTION_RENDERERS["quiz"]).
"""

import logging
import random

import requests
import streamlit as st

logger = logging.getLogger(__name__)

# Session-state keys - namespaced to avoid colliding with streamlit_app keys.
_S_PHASE = "quiz_phase"            # intro | pre | learn | post | results
_S_QUESTIONS = "quiz_questions"    # frozen list from /quiz/generate
_S_POST_ORDER = "quiz_post_order"  # shuffled presentation order for post (§3a)
_S_CURRENT = "quiz_current"
_S_PRE_ANSWERS = "quiz_pre_answers"
_S_POST_ANSWERS = "quiz_post_answers"
_S_PRE_RESULT = "quiz_pre_result"
_S_POST_RESULT = "quiz_post_result"
_S_LEARN_IDX = "quiz_learn_idx"
_S_REVIEW_DOMAINS = "quiz_review_domains"  # mastery path filter
_S_CELEBRATED = "quiz_celebrated"  # balloons fired once for this results view

# Short, 5th-grade-level praise lines for correct post-quiz answers.
_PRAISE = ["You got it!", "Nice work!", "That's right!", "Great memory!", "Well done!"]

_DOMAIN_LABELS = {
    "diagnosis": "What happened",
    "medications": "Your medications",
    "follow_up": "Follow-up visits",
    "activity": "Activity & diet",
    "red_flags": "Warning signs",
}
_DOMAIN_ICONS = {
    "diagnosis": "🫀",
    "medications": "💊",
    "follow_up": "📅",
    "activity": "🚶",
    "red_flags": "⚠️",
}


def render_quiz_tab(result: dict, session_id: str, api_base: str) -> None:
    """
    Render the teach-back quiz section for the active session.

    Args:
        result: Full PipelineResponse dict from /analyze (session state).
        session_id: pdf_session_id for this analysis - joins quiz scores to
                    the session in Neon.
        api_base: FastAPI base URL (streamlit_app._API_BASE).
    """
    phase = st.session_state.setdefault(_S_PHASE, "intro")

    if phase == "intro":
        _render_intro(result, session_id, api_base)
    elif phase in ("pre", "post"):
        _render_quiz_phase(phase, session_id, api_base)
    elif phase == "learn":
        _render_learn(result)
    else:
        _render_results()


def _reset() -> None:
    """Clear all quiz state (Start over)."""
    for key in (
        _S_PHASE, _S_QUESTIONS, _S_POST_ORDER, _S_CURRENT, _S_PRE_ANSWERS,
        _S_POST_ANSWERS, _S_PRE_RESULT, _S_POST_RESULT, _S_LEARN_IDX,
        _S_REVIEW_DOMAINS, _S_CELEBRATED,
    ):
        st.session_state.pop(key, None)


def _render_intro(result: dict, session_id: str, api_base: str) -> None:
    # Centered hero block matching the app's visual language: the plain
    # left-aligned markdown looked unfinished next to the other tabs.
    st.markdown(
        "<div style='text-align:center;padding:26px 12px 4px;'>"
        "<div style='font-size:46px;line-height:1;'>🧠</div>"
        "<h3 style='margin:12px 0 6px;'>Test your understanding</h3>"
        "<p style='margin:0;opacity:0.75;'>A short quiz about <b>your</b> "
        "discharge plan. No timers, no pressure.</p></div>",
        unsafe_allow_html=True,
    )
    step_cols = st.columns(3)
    quiz_steps = (
        ("✏️", "Answer 5 quick questions"),
        ("📖", "Learn with simple cards"),
        ("🎉", "Answer again and watch your score climb"),
    )
    for col, (icon, text) in zip(step_cols, quiz_steps):
        col.markdown(
            f"<div style='text-align:center;padding:12px 6px;opacity:0.9;'>"
            f"<div style='font-size:22px;'>{icon}</div>"
            f"<div style='font-size:13.5px;line-height:1.35;'>{text}</div></div>",
            unsafe_allow_html=True,
        )
    left_pad, center, right_pad = st.columns([1.2, 1, 1.2])
    if center.button("Start the quiz", type="primary", key="quiz_start", use_container_width=True):
        with st.spinner("Writing questions from your discharge summary..."):
            try:
                resp = requests.post(
                    f"{api_base}/quiz/generate",
                    json={
                        "session_id": session_id,
                        "extraction": result.get("extraction", {}),
                    },
                    timeout=90,
                )
                resp.raise_for_status()
                questions = resp.json().get("questions", [])
            except requests.RequestException as exc:
                logger.warning("Quiz generation failed: %s", exc)
                st.error("Could not create your quiz right now. Please try again.")
                return
        if not questions:
            st.error("Could not create your quiz right now. Please try again.")
            return
        order = list(range(len(questions)))
        random.shuffle(order)
        st.session_state[_S_QUESTIONS] = questions
        st.session_state[_S_POST_ORDER] = order
        st.session_state[_S_CURRENT] = 0
        st.session_state[_S_PRE_ANSWERS] = [None] * len(questions)
        st.session_state[_S_POST_ANSWERS] = [None] * len(questions)
        st.session_state[_S_PHASE] = "pre"
        st.rerun()


def _render_quiz_phase(phase: str, session_id: str, api_base: str) -> None:
    questions = st.session_state[_S_QUESTIONS]
    current = st.session_state[_S_CURRENT]
    is_pre = phase == "pre"
    q_index = current if is_pre else st.session_state[_S_POST_ORDER][current]
    answers_key = _S_PRE_ANSWERS if is_pre else _S_POST_ANSWERS
    question = questions[q_index]

    label = "Before you learn" if is_pre else "After learning"
    st.markdown(f"**{label} - question {current + 1} of {len(questions)}**")
    st.progress((current + 1) / len(questions))

    domain = question.get("domain", "diagnosis")
    st.caption(f"{_DOMAIN_ICONS.get(domain, '❓')} {_DOMAIN_LABELS.get(domain, domain)}")
    st.markdown(f"#### {question['question']}")

    choice = st.radio(
        "Pick one answer:",
        options=range(len(question["options"])),
        format_func=lambda i: question["options"][i],
        index=None,
        key=f"quiz_radio_{phase}_{q_index}",
        label_visibility="collapsed",
    )
    if choice is not None:
        st.session_state[answers_key][q_index] = choice
        # Post phase teaches: reveal correctness + explanation immediately.
        # Pre phase must not (§3a) - the baseline can't be a lesson.
        if not is_pre:
            if choice == question["correct_index"]:
                praise = _PRAISE[hash(question["question"]) % len(_PRAISE)]
                st.success(f"⭐ {praise} {question['explanation']}")
                # Accuracy streak (no timers, no speed points): derived from
                # the answers themselves so Streamlit reruns can't double-count.
                streak = _streak_through(questions, st.session_state[_S_POST_ORDER],
                                         st.session_state[answers_key], current)
                if streak >= 2:
                    st.markdown(f"🔥 **{streak} in a row!**")
            else:
                st.error(
                    f"The answer is: **{question['options'][question['correct_index']]}**. "
                    f"{question['explanation']}"
                )

    last = current >= len(questions) - 1
    next_label = (
        "Next" if not last
        else ("Finish & start learning" if is_pre else "See my results")
    )
    if st.button(next_label, type="primary", disabled=choice is None, key=f"quiz_next_{phase}_{current}"):
        if not last:
            st.session_state[_S_CURRENT] = current + 1
        else:
            _finish_phase(phase, session_id, api_base)
        st.rerun()


def _finish_phase(phase: str, session_id: str, api_base: str) -> None:
    """Score the finished phase (server-side, local fallback) and advance."""
    questions = st.session_state[_S_QUESTIONS]
    answers_key = _S_PRE_ANSWERS if phase == "pre" else _S_POST_ANSWERS
    answers = [a if a is not None else -1 for a in st.session_state[answers_key]]
    keys = [
        {"domain": q["domain"], "correct_index": q["correct_index"]} for q in questions
    ]
    try:
        resp = requests.post(
            f"{api_base}/quiz/score",
            json={
                "session_id": session_id,
                "phase": phase,
                "question_keys": keys,
                "answers": answers,
            },
            timeout=30,
        )
        resp.raise_for_status()
        scored = resp.json()
    except requests.RequestException as exc:
        logger.warning("Quiz scoring failed - scoring locally: %s", exc)
        scored = _score_locally(phase, keys, answers)

    if phase == "pre":
        st.session_state[_S_PRE_RESULT] = scored
        st.session_state[_S_LEARN_IDX] = 0
        st.session_state[_S_REVIEW_DOMAINS] = set()
        st.session_state[_S_CURRENT] = 0
        st.session_state[_S_PHASE] = "learn"
    else:
        st.session_state[_S_POST_RESULT] = scored
        st.session_state[_S_PHASE] = "results"


def _streak_through(questions: list, order: list[int], answers: list, upto: int) -> int:
    """
    Consecutive correct answers in post presentation order, ending at `upto`.

    Derived from stored answers (not incremented on events) so Streamlit's
    rerun-per-interaction model cannot double-count a streak.
    """
    streak = 0
    for pos in range(upto + 1):
        q_index = order[pos]
        answer = answers[q_index]
        if answer is not None and answer == questions[q_index]["correct_index"]:
            streak += 1
        else:
            streak = 0
    return streak


def _score_locally(phase: str, keys: list[dict], answers: list[int]) -> dict:
    """Offline fallback mirroring services/quiz.py - flow must never dead-end."""
    score = 0
    domains: dict[str, dict[str, int]] = {}
    for key, answer in zip(keys, answers):
        bucket = domains.setdefault(key["domain"], {"correct": 0, "total": 0})
        bucket["total"] += 1
        if answer == key["correct_index"]:
            score += 1
            bucket["correct"] += 1
    return {
        "phase": phase,
        "score": score,
        "total": len(keys),
        "percent": round(100.0 * score / len(keys), 1),
        "domain_scores": domains,
        "failed_domains": [d for d, b in domains.items() if b["correct"] < b["total"]],
        "comprehension_delta": None,
    }


def _learn_cards(result: dict) -> list[tuple[str, str]]:
    """Build (domain, content) learning cards from the pipeline result."""
    ex = result.get("extraction", {}) or {}

    def bullets(values: list | None) -> str:
        return "\n".join(f"- {v}" for v in (values or []))

    meds = "\n".join(
        f"- **{m.get('name', '')}**"
        + (f" - {m['dose']}" if m.get("dose") else "")
        + (f", {m['frequency']}" if m.get("frequency") else "")
        for m in (ex.get("medications") or [])
    )
    appts = "\n".join(
        f"- {a.get('provider') or a.get('specialty') or 'Appointment'}"
        + (f" - {a['date']}" if a.get("date") else "")
        for a in (ex.get("follow_up_appointments") or [])
    )
    cards = [
        ("diagnosis", result.get("diagnosis_explanation", "")),
        ("medications", "\n\n".join(s for s in (meds, result.get("medication_rationale", "")) if s)),
        ("follow_up", appts),
        ("activity", "\n\n".join(s for s in (
            bullets(ex.get("activity_restrictions")),
            bullets(ex.get("dietary_restrictions")),
            result.get("recovery_trajectory", ""),
        ) if s)),
        ("red_flags", "\n\n".join(s for s in (
            bullets(ex.get("red_flag_symptoms")),
            result.get("escalation_guide", ""),
        ) if s)),
    ]
    review = st.session_state.get(_S_REVIEW_DOMAINS) or set()
    filtered = [
        (d, c) for d, c in cards
        if c.strip() and (not review or d in review)
    ]
    # A failed domain with no card content must not brick the mastery loop.
    return filtered or [(d, c) for d, c in cards if c.strip()]


def _render_learn(result: dict) -> None:
    cards = _learn_cards(result)
    idx = min(st.session_state.get(_S_LEARN_IDX, 0), len(cards) - 1)
    domain, content = cards[idx]
    reviewing = bool(st.session_state.get(_S_REVIEW_DOMAINS))

    st.markdown(
        f"**{'Focused review - the parts to master' if reviewing else 'Learning time'}"
        f" - card {idx + 1} of {len(cards)}**"
    )
    st.progress((idx + 1) / len(cards))
    with st.container(border=True):
        st.markdown(f"#### {_DOMAIN_ICONS.get(domain, '📖')} {_DOMAIN_LABELS.get(domain, domain)}")
        st.markdown(content)

    back_col, _, next_col = st.columns([1, 2, 2])
    with back_col:
        if idx > 0 and st.button("Back", key=f"quiz_learn_back_{idx}"):
            st.session_state[_S_LEARN_IDX] = idx - 1
            st.rerun()
    with next_col:
        last = idx >= len(cards) - 1
        if st.button(
            "I'm ready - quiz me again" if last else "Got it, next",
            type="primary",
            key=f"quiz_learn_next_{idx}",
        ):
            if last:
                order = list(range(len(st.session_state[_S_QUESTIONS])))
                random.shuffle(order)
                st.session_state[_S_POST_ORDER] = order
                st.session_state[_S_POST_ANSWERS] = [None] * len(order)
                st.session_state[_S_CURRENT] = 0
                st.session_state[_S_PHASE] = "post"
            else:
                st.session_state[_S_LEARN_IDX] = idx + 1
            st.rerun()


def _render_results() -> None:
    pre = st.session_state.get(_S_PRE_RESULT) or {}
    post = st.session_state.get(_S_POST_RESULT) or {}
    pre_pct = float(pre.get("percent", 0.0))
    post_pct = float(post.get("percent", 0.0))
    lift = post_pct - pre_pct

    st.markdown("### Your results")
    a, b, c = st.columns(3)
    a.metric("Before learning", f"{pre_pct:.0f}%")
    b.metric("After learning", f"{post_pct:.0f}%", delta=f"{lift:+.0f} pts")
    c.metric("Score", f"{post.get('score', 0)}/{post.get('total', 0)}")

    if lift > 0:
        st.success(f"🎉 Your understanding went up **{lift:.0f} points**!")
    elif not post.get("failed_domains"):
        st.success("💯 You understood every topic - great job!")

    # Celebration gating (mirrors the mobile app): balloons only when
    # comprehension improved or the score is perfect, and only once per
    # results view so reruns don't spam the animation.
    if (lift > 0 or post_pct >= 100) and not st.session_state.get(_S_CELEBRATED):
        st.session_state[_S_CELEBRATED] = True
        st.balloons()

    st.markdown("**How you did by topic**")
    for domain, bucket in (post.get("domain_scores") or {}).items():
        full = bucket["correct"] == bucket["total"]
        st.markdown(
            f"{'✅' if full else '🟡'} {_DOMAIN_ICONS.get(domain, '')} "
            f"{_DOMAIN_LABELS.get(domain, domain)}: {bucket['correct']}/{bucket['total']}"
        )

    failed = post.get("failed_domains") or []
    if failed:
        label = "the tricky topic" if len(failed) == 1 else "the tricky topics"
        if st.button(f"Review {label} and try again", type="primary", key="quiz_mastery"):
            st.session_state[_S_REVIEW_DOMAINS] = set(failed)
            st.session_state[_S_LEARN_IDX] = 0
            st.session_state[_S_PHASE] = "learn"
            # A mastery retake earns a fresh celebration if it improves things.
            st.session_state.pop(_S_CELEBRATED, None)
            st.rerun()
    else:
        st.info("Share what you learned with a family member - teaching it back is the best proof you've got it.")

    if st.button("Start over", key="quiz_reset"):
        _reset()
        st.rerun()
