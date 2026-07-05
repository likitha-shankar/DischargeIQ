# Task 1.1 — Infrastructure and Connection Pooling ✅

**Deliverable:** Neon Serverless PostgreSQL with pooling that survives Cloud
Run autoscaling; structured-metadata-only schema (raw PHI storage forbidden).

**Commits:** Week-0 baseline; `796c526` (lifespan-scoped DB pool, pre-engagement).

**What exists:** `dischargeiq/db/history.py` (pool + discharge_history),
`db/quiz.py` (quiz_scores), `synthetic_corpus` table (task 1.6). Pool created
once at FastAPI startup, closed at shutdown — no per-request pools.

**Demo:** `GET /health` on the Cloud Run URL; show Neon tables contain only
structured fields and hashes, never document text.
