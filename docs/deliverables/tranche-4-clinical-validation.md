# Tranche 4 - Clinical Validation (End of Week 12)

**Accepted when:** the clinician review is complete at median ≥ 4.0/5.0;
zero hallucinations in the adversarial audit; integration-readiness docs
delivered.

> **Corpus decision pending (July 30 2026).** The primary testing corpus is
> now 106 real MTSamples documents, but those frequently lack follow-up
> dates and structured medication lists. Fix the scored corpus and the
> rubric wording before clinician onboarding, so reviewers judge extraction
> accuracy rather than the source document's own gaps. The locked 50-document
> synthetic set remains available under `task-4.4-corpus-lock`.

| Piece | Status |
|---|---|
| Two-clinician review of the locked corpus | ◻ Sprint 5 - scored-corpus choice open |
| Adversarial safety audit (zero hallucinations) | ◻ Sprint 5 - unblocked July 30 2026 (billing restored, backend on Vertex); run outstanding |
| Production app builds | ◻ Sprint 6 - store-signed builds out of scope (no paid accounts); release APK + 7-day iOS build instead |
| Integration-readiness docs + Vertex/BAA runbook | ◻ Sprint 6 (Vertex code path already shipped) |
| Final summary report with the measured comprehension lift | ◻ Sprint 6 |

Sprint files: [sprint-5.md](sprint-5.md) · [sprint-6.md](sprint-6.md)
