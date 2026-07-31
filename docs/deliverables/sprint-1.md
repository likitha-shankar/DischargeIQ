# Sprint 1 - Cloud Backend and Extraction Pipeline (Weeks 1–2) ✅

**Milestone contribution:** discharge text in → structured, safety-gated,
6th-grade output back, on a live cloud backend, with model failover and a
populated 50-document testing matrix.

## Tasks and commits

| Task | Deliverable | Commits | Detail |
|---|---|---|---|
| 1.1 | GCP/Neon infrastructure, pooled DB, PHI-free schema | Week-0 baseline + `796c526` | [task-1.1](tasks/task-1.1.md) |
| 1.2 | FastAPI on Cloud Run | Week-0 baseline (live URL) | [task-1.2](tasks/task-1.2.md) |
| 1.3 | Supervisor/router agent | `220c118` | [task-1.3](tasks/task-1.3.md) |
| 1.4 | Model routing: Claude failover + Vertex AI path + FK gate | `26a761a`, `b2e07b2` | [task-1.4](tasks/task-1.4.md) |
| 1.5 | 50-doc synthetic corpus | `42d0f43` (generator), `ddad5bb` (data) | [task-1.5](tasks/task-1.5.md) |
| 1.6 | Neon corpus load | `b8d2cdf` | [task-1.6](tasks/task-1.6.md) |
| - | Pre-sprint code hygiene (FK logging consolidation, dead code removal) | `806fa0b` | - |

## Demo script (bi-weekly demo)

1. Upload a synthetic discharge PDF → six plain-language sections render.
2. Upload a non-discharge PDF (e.g. a resume) → router rejects it with a
   human-readable reason instead of burning 6 agent calls.
3. Break `GOOGLE_API_KEY` in `.env`, re-run → pipeline completes on Claude
   (watch the failover log line). Restore the key.
4. Show the testing corpus. As of July 30 2026 this is
   `test-data/mtsamples/` (106 real de-identified documents, rebuilt with
   `python3 scripts/build_mtsamples_corpus.py` since the folder is
   gitignored). The original 50-document synthetic corpus and its
   `synthetic_corpus` Neon table still exist as the version-locked set;
   restore the files with
   `git checkout task-4.4-corpus-lock -- test-data/synthetic` if the demo
   calls for showing the locked corpus instead.
5. `python -m pytest dischargeiq/tests/` → all deterministic tests green.

**Checkout point:** `git checkout sprint-1-complete`
