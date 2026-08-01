# Sprint 3 - Teach-Back Evidence and Clinician Dashboard (Weeks 7-10, closes Tue 15 Sep 2026) ◻

Task IDs follow `docs/DischargeIQ_WorkPlan_v2.pdf`.

**Checkpoint 3 accepted when:** the Sprint 3 demo runs live across phone and
dashboard, all six steps; the full 50-document automated accuracy run is
complete, with results.

| Task | Deliverable | Status |
|---|---|---|
| 3.1 | Clinician dashboard, minimum functions: anonymised sessions, deltas, flagged gaps, random-sample review queue | ✅ built early `d86fc3c` - [task-3.3](tasks/task-3.3.md) |
| 3.2 | Media path executed per the 2.4 findings (per-case Gemini TTS behind a validated endpoint) | ◑ endpoint, per-diagnosis strategy, and NotebookLM-ready sources built; the actual audio generation remains - [task-4.1](tasks/task-4.1.md) |
| 3.3 | Media fallback: teach-back completes when media is absent | ✅ `dischargeiq/tests/test_media_fallback.py` - three forced failure modes |
| 3.4 | Full-corpus automated accuracy run: output-to-source diffing, readability logging, chat-grounding | ◻ **not yet run end to end.** Suite exists; quota is the constraint |
| 3.5 | Prompt tuning against the domains real testers failed | ◻ evidence pipeline shipped (`evaluation/quiz_gap_report.py`, `aef022a`); blocked on tester data from 2.6 |

## Corpus decision affecting 3.4

The plan says "all 50 corpus documents". The primary corpus is now 106 real
de-identified MTSamples documents, and the locked 50-document synthetic set
remains available under `task-4.4-corpus-lock`. Decide which the accuracy run
reports on, and say so in the results - the two measure different things.
Real documents test robustness; the synthetic set tests extraction accuracy
against known-complete inputs.
