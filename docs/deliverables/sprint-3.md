# Sprint 3 — Teach-Back Loop and Clinician Dashboard (Weeks 5–6) — core built EARLY ✅

The comprehension-lift loop was pulled forward from Week 5 to Week 2 because
it is the headline metric (13% → 50–70%).

## Tasks and commits

| Task | Deliverable | Commits | Detail |
|---|---|---|---|
| 3.1 | Quiz engine: 5 non-leading MCQs across 5 domains, scores schema, pre/post protocol | `7efc3b7` | [task-3.1](tasks/task-3.1.md) |
| 3.2 | Gamified UI: mobile app tab + Streamlit fallback tab, mastery paths | `a7359fc`, `de6d126` | [task-3.2](tasks/task-3.2.md) |
| 3.3 | Streamlit clinician dashboard (deltas, flagged gaps, read replica) | ✅ | [task-3.3](tasks/task-3.3.md) |
| 3.4 | Prompt tuning on real tester data | ◻ tooling ready; tuning needs Sprint 2 testers |

## Demo script

1. Analyze a discharge PDF on the phone (or Streamlit fallback).
2. "Test yourself" tab → baseline quiz (note: no right/wrong feedback — the
   baseline must not teach, per protocol §3a).
3. Learning cards → post-quiz (same questions, shuffled, instant feedback).
4. Results: score ring, before/after lift banner, per-domain chips.
5. Miss a question on purpose → mastery path forces focused review of just
   that topic before retake.
6. Show the `quiz_scores` rows in Neon: pre, post, and the computed delta.

Verified live on July 5: pre 40% → post 100%, comprehension_delta 60.0
computed server-side from the Neon-stored baseline.

**Checkout points:** `task-3.1-quiz-backend`, `task-3.2-quiz-mobile`, `task-3.2-quiz-web`
