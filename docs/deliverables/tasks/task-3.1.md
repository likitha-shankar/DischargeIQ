# Task 3.1 - Teach-Back Quiz Logic ✅ (built early, Week 2)

**Deliverable:** the comprehension-lift engine - schema for pre/post scores,
Agent-generated non-leading MCQs from the extracted discharge data.

**Commit / tag:** `7efc3b7` / `task-3.1-quiz-backend`

**Design (protocol §3a):**
- `quiz_agent.py` + prompt: exactly 5 four-option MCQs, one per comprehension
  domain (diagnosis, medications, follow_up, activity, red_flags), grounded
  ONLY in the patient's extracted data, 6th-grade language, FK-scored.
- Frozen set per session - identical questions pre and post so the delta
  measures the intervention.
- `POST /quiz/generate` and `POST /quiz/score`: stateless (client carries the
  grading key) → safe under Cloud Run multi-instance routing. Rate-limited.
- `quiz_scores` table: structured fields only; the FIRST pre score is the
  honest baseline; delta computed server-side on post phases.
- 12 deterministic tests.

**Verified live:** pre 40% → post 100%, comprehension_delta 60.0 from the
Neon-stored baseline.
