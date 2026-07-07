"""
File: ui/quiz_tab.py
Owner: Likitha Shankar
Description: "Test yourself" tab for the Streamlit fallback surface (Sprint 3,
  Task 3.2) - the same teach-back loop as the mobile app: baseline quiz (no
  feedback) → learning cards → post-quiz (feedback + explanations) → results
  with the comprehension lift. Mirrors the mobile flow so demos are equivalent
  on either surface; the phone app remains the primary product.
Key functions/classes: render_quiz_tab
Game layer (v3, mirrors the mobile app): XP + levels, per-domain mastery
  badges, session-scoped personal bests, and a "Master it" retake that
  re-asks only the missed questions. Game state lives in st.session_state
  (the fallback surface has no device storage); the phone app persists the
  same state on-device via game_store.dart.
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
_S_MASTERY_ROUND = "quiz_mastery_round"  # post round re-asks only missed questions
_S_ROUND_NONCE = "quiz_round_nonce"  # bumped per post round → fresh widget keys
_S_XP_GAINED = "quiz_xp_gained"    # XP earned by the round just scored
# Game stats survive "Start over" - they are cross-quiz engagement state.
_S_GAME = "quiz_game_stats"

# XP rules and level thresholds - keep in sync with the mobile app
# (dischargeiq_mobile/lib/services/game_store.dart). Accuracy-based only:
# no speed bonuses, which pressure older or unwell patients.
_XP_PER_CORRECT = 10
_XP_QUIZ_FINISHED = 25
_XP_ALL_MASTERED = 50
_LEVEL_THRESHOLDS = [0, 100, 250, 450, 700, 1000, 1400, 1900]

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
    """Clear per-quiz state (Start over). Game stats (_S_GAME) survive -
    XP and personal bests span quizzes by design."""
    for key in (
        _S_PHASE, _S_QUESTIONS, _S_POST_ORDER, _S_CURRENT, _S_PRE_ANSWERS,
        _S_POST_ANSWERS, _S_PRE_RESULT, _S_POST_RESULT, _S_LEARN_IDX,
        _S_REVIEW_DOMAINS, _S_CELEBRATED, _S_MASTERY_ROUND, _S_XP_GAINED,
        _S_ROUND_NONCE,
    ):
        st.session_state.pop(key, None)


def _game() -> dict:
    """Session-scoped game stats, created on first use."""
    return st.session_state.setdefault(_S_GAME, {
        "xp": 0, "quizzes": 0, "best_post": 0.0, "best_lift": 0.0,
        "mastered": set(), "history": [],  # newest-first [(pre, post), ...]
    })


def _level(xp: int) -> int:
    """1-based level for a cumulative XP total."""
    return sum(1 for t in _LEVEL_THRESHOLDS if xp >= t) or 1


def _level_progress(xp: int) -> tuple[float, int]:
    """(progress 0..1 toward the next level, XP still needed); (1.0, 0) at max."""
    lvl = _level(xp)
    if lvl >= len(_LEVEL_THRESHOLDS):
        return 1.0, 0
    floor, ceil = _LEVEL_THRESHOLDS[lvl - 1], _LEVEL_THRESHOLDS[lvl]
    return (xp - floor) / (ceil - floor), ceil - xp


def _render_intro(result: dict, session_id: str, api_base: str) -> None:
    # Returning player (this browser session): level + personal bests.
    game = _game()
    if game["quizzes"] > 0:
        best_lift = game["best_lift"]
        st.info(
            f"🏅 Welcome back - **Level {_level(game['xp'])}**   ·   "
            f"Personal best: **{game['best_post']:.0f}%**"
            + (f"   ·   Biggest jump: **+{best_lift:.0f} pts**" if best_lift > 0 else "")
            + f"   ·   Quizzes done: {game['quizzes']}"
        )
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

    # A mastery round re-asks only the missed questions, so the round is the
    # post order's length, not the full question count.
    round_len = len(questions) if is_pre else len(st.session_state[_S_POST_ORDER])
    label = (
        "Before you learn" if is_pre
        else ("Master it" if st.session_state.get(_S_MASTERY_ROUND) else "After learning")
    )
    st.markdown(f"**{label} - question {current + 1} of {round_len}**")
    st.progress((current + 1) / round_len)

    domain = question.get("domain", "diagnosis")
    st.caption(f"{_DOMAIN_ICONS.get(domain, '❓')} {_DOMAIN_LABELS.get(domain, domain)}")
    st.markdown(f"#### {question['question']}")

    choice = st.radio(
        "Pick one answer:",
        options=range(len(question["options"])),
        format_func=lambda i: question["options"][i],
        index=None,
        # The nonce keeps a mastery round's radios fresh - reusing the first
        # post round's key would resurface the stale (wrong) selection.
        key=f"quiz_radio_{phase}_{st.session_state.get(_S_ROUND_NONCE, 0)}_{q_index}",
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

    last = current >= round_len - 1
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
        _award_xp(scored)
        st.session_state[_S_POST_RESULT] = scored
        st.session_state[_S_PHASE] = "results"


def _award_xp(scored: dict) -> None:
    """
    Fold the just-scored post round into the session game stats.

    XP counts only questions ASKED this round (the post order), so a mastery
    retake cannot re-earn XP for answers carried over as correct. The
    full-mastery bonus fires only on the transition into mastery. Mirrors
    _awardXpAndPersist in the mobile app's quiz_screen.dart.
    """
    game = _game()
    questions = st.session_state[_S_QUESTIONS]
    answers = st.session_state[_S_POST_ANSWERS]
    gained = _XP_QUIZ_FINISHED + sum(
        _XP_PER_CORRECT
        for i in st.session_state[_S_POST_ORDER]
        if answers[i] == questions[i]["correct_index"]
    )
    previous = st.session_state.get(_S_POST_RESULT) or {}
    was_mastered = previous != {} and not previous.get("failed_domains")
    if not scored.get("failed_domains") and not was_mastered:
        gained += _XP_ALL_MASTERED
    game["xp"] += gained
    for domain, bucket in (scored.get("domain_scores") or {}).items():
        if bucket["correct"] == bucket["total"]:
            game["mastered"].add(domain)
    post_pct = float(scored.get("percent", 0.0))
    if st.session_state.get(_S_MASTERY_ROUND):
        # A mastery retake only improves bests; the run was already recorded.
        game["best_post"] = max(game["best_post"], post_pct)
    else:
        pre_pct = float((st.session_state.get(_S_PRE_RESULT) or {}).get("percent", 0.0))
        game["quizzes"] += 1
        game["best_post"] = max(game["best_post"], post_pct)
        game["best_lift"] = max(game["best_lift"], post_pct - pre_pct)
        game["history"].insert(0, (pre_pct, post_pct))
        del game["history"][20:]
    st.session_state[_S_XP_GAINED] = gained


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
                _start_post_round()
            else:
                st.session_state[_S_LEARN_IDX] = idx + 1
            st.rerun()


def _start_post_round() -> None:
    """
    Enter the post phase. After a mastery review, re-ask ONLY the questions
    missed in the last post round - correct answers carry over untouched, so
    the retake is short and winnable. First post round asks everything.
    """
    questions = st.session_state[_S_QUESTIONS]
    answers = st.session_state[_S_POST_ANSWERS]
    reviewing = bool(st.session_state.get(_S_REVIEW_DOMAINS))
    missed = (
        [i for i, q in enumerate(questions) if answers[i] != q["correct_index"]]
        if reviewing and st.session_state.get(_S_POST_RESULT) else []
    )
    if missed:
        st.session_state[_S_MASTERY_ROUND] = True
        for i in missed:
            answers[i] = None
        random.shuffle(missed)
        st.session_state[_S_POST_ORDER] = missed
    else:
        st.session_state[_S_MASTERY_ROUND] = False
        order = list(range(len(questions)))
        random.shuffle(order)
        st.session_state[_S_POST_ORDER] = order
        st.session_state[_S_POST_ANSWERS] = [None] * len(order)
    st.session_state[_S_ROUND_NONCE] = st.session_state.get(_S_ROUND_NONCE, 0) + 1
    st.session_state[_S_CURRENT] = 0
    st.session_state[_S_PHASE] = "post"


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

    # Game layer: XP earned this round + level progress.
    game = _game()
    gained = st.session_state.get(_S_XP_GAINED, 0)
    progress, to_next = _level_progress(game["xp"])
    st.markdown(
        f"⚡ **+{gained} XP**   ·   🏅 **Level {_level(game['xp'])}**"
        + (f" - {to_next} XP to the next level" if to_next else " - top level!")
    )
    st.progress(progress)

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
    # Three-step mastery ladder per domain; a badge earned in any earlier
    # quiz this session never downgrades (non-punitive, mirrors mobile).
    for domain, bucket in (post.get("domain_scores") or {}).items():
        if domain in game["mastered"] or bucket["correct"] == bucket["total"]:
            icon, label = "🏆", "Mastered"
        elif bucket["correct"] * 2 >= bucket["total"]:
            icon, label = "🟢", "Almost there"
        else:
            icon, label = "🟡", "Keep learning"
        st.markdown(
            f"{icon} {_DOMAIN_ICONS.get(domain, '')} "
            f"{_DOMAIN_LABELS.get(domain, domain)} - {label} "
            f"({bucket['correct']}/{bucket['total']})"
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
