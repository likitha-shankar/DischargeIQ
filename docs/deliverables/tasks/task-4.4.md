# Task 4.4 - Lock the 50-Document Clinical-Trial Corpus ✅

**Deliverable:** the synthetic corpus is version-locked so clinician review
(Sprint 5) scores map to an immutable document set. Any later change to a
corpus PDF is detectable and fails verification.

**Commit / tag:** pending review - suggested tag `task-4.4-corpus-lock`

**How it works (`scripts/lock_corpus.py`):**
- SHA-256 per PDF + a single `combined_hash` fingerprint over all 50 files.
- Cross-checks the PDF set against `corpus_index.json` - a silently added or
  dropped file fails the lock (`missing PDFs` / `unindexed PDFs`).
- Writes `test-data/synthetic/corpus_lock.json` (the frozen contract, tracked
  in git): `corpus_size`, `combined_hash`, per-file hashes, `locked_at`.
- `--verify` (no writes, exit 1 on drift) names exactly which files changed,
  added, or removed - so a reviewer knows which scores to redo. Safe for CI
  or a pre-review check.

**Verified:** locked 50 files (`combined_hash 4f0b4250...`); `--verify` clean
on the untouched corpus; a one-byte tamper to `copd_01.pdf` was correctly
reported as `changed` with exit 1, and restore returned to clean.

**Note:** the guide schedules the formal lock for Week 8. The tooling and
lockfile are ready now; re-run `python scripts/lock_corpus.py` if the corpus
is regenerated before then, and treat the Week-8 lock as final.
