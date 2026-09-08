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
| 3.4 | Full-corpus automated accuracy run: output-to-source diffing, readability logging, chat-grounding | ✅ **complete on 106 of 106**, 31 Aug 2026. Report: `evaluation/corpus_accuracy_report.md`. Coverage closed; the open item is now stratum breadth, not count |
| 3.5 | Prompt tuning against the domains real testers failed | ◻ evidence pipeline shipped (`evaluation/quiz_gap_report.py`, `aef022a`); blocked on tester data from 2.6 |

## What the 3.4 run actually found (31 Aug, 106 documents)

Full report: `evaluation/corpus_accuracy_report.md`. Superseded the 16 Aug
55-document run; the numbers below are the ones to quote.

- **Readability passes.** 98% of 424 outputs meet FK <= 6.0, mean grade 4.08.
- **Medication grounding is clean: 0** medication names absent from source
  across all 106. That is the Agent 1 contract holding.
- **Omission, reported separately from fluency** (Liebovitz 2.5): medication
  recall 529/532 (99.4%), warning-sign recall 89/95 (93.7%). The three dropped
  medications and six dropped warning signs are named individually in the
  report. This is the half a readability score cannot see.
- **Numeric grounding: 25 of 106** outputs contain a number not in the source.
  22 are prompt-supplied clinical thresholds; 3 are activity targets the model
  invented because the Agent 4 prompt required a weekly goal when the source
  set none. Both classes were fixed on 25 Aug - on a 10-document verification
  set, documents carrying an invented value went from 8/10 to 0/10.
- **Pipeline completion: 106/106.** 104 `complete_with_warnings` (every agent
  ran, the source was missing sections), 2 `complete`.

Whether a general fever threshold may be shown to a patient as if their own
paperwork said so remains a clinical call, not a prompt-file call. **Still the
first item for task 4.2 review.**

Consequence for Checkpoint 4: the "98-100% accuracy on tested content" bar is
met on readability and on medication fidelity. Say which is being certified.

## Coverage closed, breadth still open

The count gap is closed: **106 of 106**. The remaining weakness is not how
many documents but how few KINDS. Every one of the 106 is a dictated
transcription, so all of the above generalises to dictated documents only -
which is exactly Liebovitz item 3.3 and the LOF stratified-testing request.

A degraded stratum exists at `test-data/fax/` (`scripts/build_fax_stratum.py`)
and is the open work. It simulates OCR damage rather than being a real scan,
so it gives a lower bound, not a fax measurement - and must never be described
as one.

Historical note, kept because it explains the delay: the nightly
`corpus_catchup.sh` cron **never ran** (macOS TCC blocking `/usr/sbin/cron` on
a `~/Desktop` path) and was disabled on 25 Aug ahead of a demo. Also
established that day: `gemini-2.5-flash-lite` on Vertex runs on **dynamic
shared quota** with no per-project limit, so the 429s throttling the run could
not be paced away and no quota increase could be requested. The remaining
documents were worked through in supervised batches.

## Corpus decision affecting 3.4

The plan says "all 50 corpus documents". The primary corpus is now 106 real
de-identified MTSamples documents, and the locked 50-document synthetic set
remains available under `task-4.4-corpus-lock`. Decide which the accuracy run
reports on, and say so in the results - the two measure different things.
Real documents test robustness; the synthetic set tests extraction accuracy
against known-complete inputs.
