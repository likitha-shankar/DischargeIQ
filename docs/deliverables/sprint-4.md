# Sprint 4 - NotebookLM Media and Corpus Lock (Weeks 7–8) ◻

| Task | Deliverable | Status |
|---|---|---|
| 4.1 | Media generation workflow (care plan → NotebookLM audio/video → app) | ◑ scaffolding built early - [task-4.1](tasks/task-4.1.md): per-diagnosis strategy, `/media/{document_type}` endpoint, Streamlit player with text fallback. Remaining: generate the 5 NotebookLM audios |
| 4.2 | Media quality pass (pronunciation, source formatting) | ◑ - NotebookLM-ready source docs built for all 5 diagnoses (`dischargeiq/media/sources/`): reviewed template text verbatim, reformatted with bulleting + phonetic hints (the pacing/pronunciation lever). Remaining: run the actual audio generation + listen-through |
| 4.3 | Spanish support (stretch, cut first if velocity slips) | ◻ |
| 4.4 | Lock the clinical trial corpus | ✅ tooling ready - [task-4.4](tasks/task-4.4.md): `scripts/lock_corpus.py` + `corpus_lock.json` (SHA-256 per file + combined hash, `--verify` drift check). **Corpus changed July 30 2026** to the 106-document MTSamples set; point the locker at `--corpus-dir test-data/mtsamples` when freezing at Week 8. The previous 50-document synthetic lock (combined hash `4f0b4250…`) stays valid under tag `task-4.4-corpus-lock`. |

Fallback rule (also Sprint 6 task 6.5): media failure always degrades to the
text-only teach-back loop - the comprehension metric is never blocked by media.
