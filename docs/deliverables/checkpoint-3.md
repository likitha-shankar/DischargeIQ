# Checkpoint 3 - Week 10, Tue 15 Sep 2026 - $1,250 ◻

**Accepted when:** the Sprint 3 demo runs live across the phone and
dashboard, all six steps. The full 50-document automated accuracy run is
complete, with results.

Program gate: Gate 3, feature-complete beta - all approved scope present,
stable, demo-able without major gaps. This is the main quality filter; see
the Gate 3 checklist in `docs/LOF_LABS_RULES.md`.

| Piece | Status |
|---|---|
| Clinician dashboard with random-sample review queue | ✅ built early |
| Media path executed per the 2.4 findings | ✅ all five diagnoses generated 16 Aug `b12c752`, Google Cloud TTS on ADC |
| Text-only fallback proven on three failure modes | ✅ |
| Full-corpus automated accuracy run with results | ✅ **complete on 106 of 106 documents**, 31 Aug 2026, `evaluation/corpus_accuracy_report.md`. Readability 98% of 424 outputs (mean grade 4.08); 0 medication names absent from source; 25 outputs carry a number the source did not. Caveat: all 106 are dictated transcriptions, so the figures generalise to one stratum |
| Measured comprehension deltas from real testers | ◻ depends on Checkpoint 2 recruiting |
| Prompt tuning traced to tester failures | ◻ pipeline ready, needs the data |

Sprint file: [sprint-3.md](sprint-3.md) ◻
