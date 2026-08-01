# Task 5.1 - Clinician Review Portal (built early) ✅

**Deliverable:** role-gated Streamlit portal where two clinicians independently
score the locked 50-document corpus outputs on a 0-5 rubric with a
zero-tolerance hallucination flag - the instrument that produces the final-demo
gate evidence (median ≥ 4.0, zero hallucinations).

**Commit / tag:** `a5f5f43` / `task-5.1-clinician-review`

**Design:**
- Separate Streamlit entry (`ui/clinician_review.py`, port 8503). Run:
  `streamlit run ui/clinician_review.py --server.port 8503`.
- **Frozen review set:** `scripts/run_corpus_for_review.py` runs the full
  pipeline over `test-data/synthetic/*.pdf` and writes one JSON per document
  to `evaluation/corpus_outputs/`. Resumable (skips existing files); reviewers
  score a frozen set, never live regenerations. Repo rule respected: agent
  free-text lives on disk, ONLY structured scores go to Neon.
- **Access model (fail-closed):** portal refuses to open unless
  `CLINICIAN_ACCESS_CODE` is set in `.env`; reviewers enter the shared code +
  their name. Real per-user auth is deferred to the security pass.
- **Rubric:** single 0-5 score with anchor sentences per grade (5 = "would
  hand to my own patient unchanged", 0 = unusable), a hallucination checkbox
  (any med/dose/diagnosis not in the source), and comments - comments are
  REQUIRED below 4 or when flagging, because Task 5.4's fix pass works from
  them. One score per (reviewer, document), re-scoring upserts.
- **Live gate sidebar:** documents scored, overall median (median of
  per-document medians so double-scored docs don't weigh twice), flagged
  hallucination docs, and the below-4.0 fix-pass worklist. `GATE PASSED`
  only at full coverage + median ≥ 4.0 + zero flags.
- Gate math lives in `ui/review_analytics.py` (Streamlit-free, same pattern
  as `quiz_analytics.py`) with unit tests in
  `dischargeiq/tests/test_review_analytics.py`.
- New table: `clinician_scores` (reviewer, doc_name, score 0-5,
  hallucination bool, comments, UNIQUE(reviewer, doc_name)).

**Operator runbook:**
1. `python scripts/run_corpus_for_review.py` (once, ~30s/doc; resumable).
2. Set `CLINICIAN_ACCESS_CODE` in `.env`, share with the two LOF reviewers.
3. `streamlit run ui/clinician_review.py --server.port 8503`.
4. Watch the gate sidebar; export worklist for Task 5.4 when scoring is done.

**Verified:** 4/4 unit tests green (rollup medians, hallucination taint,
coverage requirement, fix-pass worklist); smoke run generated
`copd_01.json` end-to-end (32s, all four agent texts present; `partial`
status comes from the document's deliberate imperfections, which is exactly
what reviewers are scoring).
