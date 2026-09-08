# Task 2.1 - Teach-Back Quiz Loop ✅

**Deliverable:** frozen baseline questions with no feedback, learning cards,
then a post-quiz, with the comprehension delta computed server-side rather
than self-reported.

**Commits:** `7efc3b7`, `a7359fc`, `de6d126`. Results sheet `455add2`.

**Endpoints:** `POST /quiz/generate` (up to 5 non-leading MCQs from the
session's extraction; questions failing validation are dropped and the agent
raises below 3, so a sparse document legitimately yields 4).
`POST /quiz/score` persists to `quiz_scores` and returns
`comprehension_delta` against the FIRST stored pre score.

## Why the baseline round is silent

The delta is only meaningful if the first round measures what the patient
understood from their own paperwork. Feedback during those questions would
teach mid-measurement. The silence is DURING the questions only - teaching
between rounds is the whole design.

## Round structure, revised 8 Sep 2026

The baseline round used to end by jumping straight to learning cards, which
from the patient's side read as the quiz having no ending: five questions
answered, and the app changed the subject.

It now ends on a **results sheet** - score, how many are worth another look,
and every question listed. Tapping one shows what they picked AND the correct
answer with its explanation; each offers the learning card for that
question's topic rather than starting the deck from the front. Both ways
forward are on the sheet, so a patient who scored well is not made to page
through five cards to continue.

This does not contaminate the measurement, for the reason above.

**Verified live:** pre 40% → post 100% (5 Jul). Generation and scoring
re-verified against the deployed service 8 Sep: 5 questions across all 5
domains, every one carrying an explanation.

## Open

Comprehension lift across real testers is still unmeasured - it depends on
task 2.6 recruiting. The per-domain gap report (`evaluation/quiz_gap_report.py`)
is built and idle, waiting on that data.
