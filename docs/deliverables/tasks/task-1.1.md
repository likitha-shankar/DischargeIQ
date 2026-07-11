# Task 1.1 - Infrastructure and Connection Pooling ✅

**Deliverable:** Neon Serverless PostgreSQL with pooling that survives Cloud
Run autoscaling; structured-metadata-only schema (raw PHI storage forbidden).

**Commits:** Week-0 baseline; `796c526` (lifespan-scoped DB pool, pre-engagement).

**What exists:** `dischargeiq/db/history.py` (pool + discharge_history),
`db/quiz.py` (quiz_scores), `synthetic_corpus` table (task 1.6). Pool created
once at FastAPI startup, closed at shutdown - no per-request pools.

## Pooler confirmation (verified Jul 8, 2026)

- Prod `DATABASE_URL` is injected from Secret Manager (secret `database-url`,
  `latest` version) - not a literal env var on the Cloud Run service.
- Secret host: `ep-plain-moon-aec14kjp-pooler.c-2.us-east-2.aws.neon.tech` -
  the `-pooler` suffix confirms Neon's built-in PgBouncer endpoint, so app-side
  asyncpg (1-5 conns per instance) sits behind PgBouncer under autoscaling.
- Local `.env` uses the same pooler host. Only hostnames were inspected;
  credentials were never printed.
- Live check same day: `GET /api/health` reports `database.reachable: true`;
  `synthetic_corpus` counts 10 rows per category (5x10 matrix intact).

**Demo:** `GET /api/health` on the Cloud Run URL (plain `/health` returns
Streamlit HTML); show Neon tables contain only structured fields and hashes,
never document text.
