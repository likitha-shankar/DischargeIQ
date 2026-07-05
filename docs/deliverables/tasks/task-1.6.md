# Task 1.6 — Neon Corpus Load ✅

**Deliverable:** corpus metadata loaded into Neon to populate the testing
matrix for Month 3's clinician review.

**Commit:** `b8d2cdf` (also the `sprint-1-complete` tag)

**Files:** `scripts/load_corpus_to_neon.py` → `synthetic_corpus` table
(doc_name natural key; re-runs upsert in place). Executed July 5: 50 rows.

**Demo:** `SELECT category, count(*) FROM synthetic_corpus GROUP BY 1;` → 5×10.
