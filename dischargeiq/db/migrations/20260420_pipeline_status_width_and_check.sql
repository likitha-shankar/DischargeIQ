-- File: dischargeiq/db/migrations/20260420_pipeline_status_width_and_check.sql
-- Owner: Likitha Shankar
-- Description: Widens pipeline_status to VARCHAR(30) so complete_with_warnings fits,
--   replaces CHECK constraint to lock allowed status strings to orchestrator values.
-- Run order: After schema.sql baseline on databases that had VARCHAR(20); idempotent
--   DROP/ADD for chk_pipeline_status.
-- Depends on: discharge_history table from dischargeiq/db/schema.sql (or equivalent).

-- Migration: widen discharge_history.pipeline_status and add a CHECK constraint.
--
-- Context:
--   The production hardening pass (2026-04-20) introduced a third pipeline
--   status value, "complete_with_warnings" (22 chars), which no longer fit in
--   the original VARCHAR(20) column. Inserts for that status were being
--   rejected by the DB with "value too long for type character varying(20)"
--   and the pipeline logged a (non-fatal) warning on every advisory-warning
--   run.
--
-- Changes:
--   1) Widen pipeline_status from VARCHAR(20) to VARCHAR(30) so
--      "complete_with_warnings" (and any future short suffix) fits.
--   2) Add a CHECK constraint locking the column to the three values the
--      orchestrator actually writes. If a future agent change introduces
--      a new status (e.g. "complete_with_errors"), the INSERT will fail
--      loudly in tests rather than silently truncating or drifting.
--
-- Canonical status values (derived from
--   grep "pipeline_status\s*=" dischargeiq/pipeline/orchestrator.py):
--   - complete                (all five agents OK, no completeness gaps)
--   - complete_with_warnings  (all agents OK, advisory gaps only)
--   - partial                 (Agent 1 critical gap OR any agent failure)
--
-- Rollout: applied to Neon on 2026-04-20 via asyncpg one-liner; this file
-- is the idempotent record so teammates pulling main can reproduce the
-- change on a fresh database.

ALTER TABLE discharge_history
  ALTER COLUMN pipeline_status TYPE VARCHAR(30);

ALTER TABLE discharge_history
  DROP CONSTRAINT IF EXISTS chk_pipeline_status;

ALTER TABLE discharge_history
  ADD CONSTRAINT chk_pipeline_status
  CHECK (pipeline_status IN (
    'complete',
    'complete_with_warnings',
    'partial'
  ));
