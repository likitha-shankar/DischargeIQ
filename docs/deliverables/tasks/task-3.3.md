# Task 3.3 — Streamlit Clinician Dashboard ✅

**Deliverable:** a clinician-facing analytics surface — anonymized session
hashes, per-session comprehension deltas, and flagged knowledge gaps — on a
read path that never touches transactional performance.

**Commit / tag:** `d86fc3c` / `task-3.3-clinician-dashboard`

**Design:**
- Separate Streamlit entry (`ui/clinician_dashboard.py`, port 8502) — NOT a
  patient tab. Run: `streamlit run ui/clinician_dashboard.py --server.port 8502`.
- Reads Neon directly via `DATABASE_URL_RO` (read replica; falls back to
  `DATABASE_URL` for dev with a visible notice). 60s cache TTL keeps replica
  load at ~1 query/min regardless of interaction.
- **Anonymization contract:** only truncated random session ids + document
  hashes are displayed. The tables it reads store no names, no document
  text, no quiz question/answer text.
- Headline tiles: documents analyzed, completed quiz loops, avg baseline %,
  avg post-teaching % with lift delta and the 50–70% target-band check.
- **Flagged gaps** = domains still missed on the POST quiz (after the
  learning cards) — the actionable signal for a care team. Baseline-vs-post
  miss rate per domain shown as a single-axis horizontal bar comparison.
- Sessions table joins `discharge_history` × `quiz_scores` using the same
  protocol as the API: FIRST pre score is the honest baseline, LAST post
  score is the outcome.

**Demo:** run a phone/Streamlit quiz loop, open the dashboard — the session
appears with its delta, and any post-quiz misses show in the flagged list.

**Verified:** live against Neon (310 sessions; the July 5 demo loop shows
pre 40% → post 100%, +60 pts; domain miss rates match the stored
`domain_scores`). Boots headless, `/healthz` ok, empty-DB and missing-table
paths return friendly notices.
