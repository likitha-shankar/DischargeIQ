# Task 1.5 — Synthetic Data Generation ✅

**Deliverable:** 50 varied synthetic discharge summaries (10 per diagnosis ×
5 conditions) with realistic 11th-grade jargon and disjointed formatting.

**Commits / tag:** `42d0f43` (generator), `ddad5bb` (data) / `task-1.5-corpus`

**Files:** `scripts/generate_synthetic_corpus.py`, `test-data/synthetic/*.pdf`,
`test-data/synthetic/corpus_index.json` (structured metadata per document).

**Safety:** fully synthetic identifiers only (Patient NN, MRN 000-TEST-NN);
resumable (skips existing files); variant seeds vary age, sex, severity,
comorbidities, and regimens.

**Demo:** open two PDFs from different categories — different header styles,
different severities; show the 10×5 category matrix.
