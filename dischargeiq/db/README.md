# `db/` — PostgreSQL persistence

Neon Postgres schema and write helpers for discharge history. Currently
**not wired into the pipeline** — the module exists as scaffolding for
future history/retrieval work.

## Files

- `schema.sql` — `discharge_history` table definition. Apply once per
  database: `psql "$DATABASE_URL" -f dischargeiq/db/schema.sql`.
- `history.py` — async write helper `save_discharge_history(...)` built
  on `asyncpg`. No callers today.

## Setup

```bash
# 1. Set DATABASE_URL in .env (Neon connection string)
# 2. Apply the schema once:
psql "$DATABASE_URL" -f dischargeiq/db/schema.sql
```

## Data policy

Never store full PDF text or free-text agent outputs here. Only
structured fields, SHA-256 document hashes, and metadata. All test
documents must be synthetic or de-identified.
