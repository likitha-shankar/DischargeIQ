# Sprint 3 - Teach-Back Evidence and Clinician Dashboard (Weeks 7-10, closes Tue 15 Sep 2026) ◻

Task IDs follow `docs/DischargeIQ_WorkPlan_v2.pdf`.

**Checkpoint 3 accepted when:** the Sprint 3 demo runs live across phone and
dashboard, all six steps; the full 50-document automated accuracy run is
complete, with results.

| Task | Deliverable | Status |
|---|---|---|
| 3.1 | Clinician dashboard, minimum functions: anonymised sessions, deltas, flagged gaps, random-sample review queue | ✅ built early `d86fc3c` - [task-3.3](tasks/task-3.3.md) |
| 3.2 | Media path executed per the 2.4 findings (per-case TTS behind a validated endpoint) | ✅ **audio generated 16 Aug** `b12c752` - all five diagnoses exist as WAVs in `dischargeiq/media/`. Delivered via **Google Cloud TTS on ADC**, not Gemini TTS on a key: the key was deleted on 16 Aug and nothing holds one now - [task-4.1](tasks/task-4.1.md) |
| 3.3 | Media fallback: teach-back completes when media is absent | ✅ `dischargeiq/tests/test_media_fallback.py` - three forced failure modes |
| 3.4 | Full-corpus automated accuracy run: output-to-source diffing, readability logging, chat-grounding | ◑ **run and reported, but on 55 of 106 documents** `23282b9`, refreshed `5fcc736`. Report: `evaluation/corpus_accuracy_report.md`. Coverage is the open item, not the tooling |
| 3.5 | Prompt tuning against the domains real testers failed | ◻ evidence pipeline shipped (`evaluation/quiz_gap_report.py`, `aef022a`); blocked on tester data from 2.6 |

## What the 3.4 run actually found (16 Aug, 55 documents)

Full report: `evaluation/corpus_accuracy_report.md`. The two headline numbers
point in opposite directions and both belong at the checkpoint.

- **Readability passes.** 99% of 220 outputs meet FK <= 6.0, mean grade 4.19.
  Agents 4 and 5 are at 55/55.
- **Medication grounding is clean: 0** medication names absent from source
  across all 55. That is the Agent 1 contract holding.
- **Numeric grounding is the open risk: 47 of 55** outputs contain a number
  not in the source document. 46 are prompt-supplied clinical thresholds
  ("over 101 F"); 38 are activity targets the model invents because the
  Agent 4 prompt *requires* a weekly goal even when the source sets none.

The second class is not a random hallucination, it is caused by a prompt
requirement, which means it is fixable. But whether a general fever threshold
may be shown to a patient as if their own paperwork said so is a clinical
call, not a prompt-file call. **This is the first item for task 4.2 review.**

Consequence for Checkpoint 4: the "98-100% accuracy on tested content" bar is
met on readability and on medication fidelity, and is **not yet demonstrated**
on numeric grounding. Say which is being certified.

## Coverage gap on 3.4

The report covers **55 of 106 documents (52%)**. Acceptance asks for a full
run, so this is not complete under any reading of the number.

The nightly `corpus_catchup.sh` cron that was meant to close the gap **never
ran** (one log in nine days, macOS TCC blocking `/usr/sbin/cron` on a
`~/Desktop` path) and was **disabled on 25 Aug** ahead of a demo. Nothing is
closing this gap automatically right now.

Also established 25 Aug: `gemini-2.5-flash-lite` on Vertex runs on **dynamic
shared quota** with no per-project limit, so the 429s throttling this run
cannot be paced away reliably and **no quota increase can be requested**.
Remaining documents have to be worked through in supervised batches.

## Corpus decision affecting 3.4

The plan says "all 50 corpus documents". The primary corpus is now 106 real
de-identified MTSamples documents, and the locked 50-document synthetic set
remains available under `task-4.4-corpus-lock`. Decide which the accuracy run
reports on, and say so in the results - the two measure different things.
Real documents test robustness; the synthetic set tests extraction accuracy
against known-complete inputs.
