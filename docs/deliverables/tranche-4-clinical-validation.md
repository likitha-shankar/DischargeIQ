# Tranche 4 - Clinical Validation (End of Week 12)

**Accepted when:** the clinician review is complete at median ≥ 4.0/5.0;
zero hallucinations in the adversarial audit; integration-readiness docs
delivered.

> **Corpus decision made (July 30 2026).** The scored corpus is the 106
> real de-identified MTSamples documents - running on real discharge
> summaries is the product goal, so validation runs on them too. The rubric
> was corrected rather than the corpus swapped: anchors now judge fidelity to
> the source, since only 34% of real documents contain warning signs at all.
> Without that change the gate would have measured the hospitals' paperwork.
> The locked 50-document synthetic set remains available under
> `task-4.4-corpus-lock` as a well-formed control if a comparison is wanted.

| Piece | Status |
|---|---|
| Two-clinician review of the locked corpus | ◻ Sprint 5 - corpus and rubric settled; awaiting reviewers |
| Adversarial safety audit (zero hallucinations) | ◻ Sprint 5 - unblocked July 30 2026 (billing restored, backend on Vertex); run outstanding |
| Production app builds | ◻ Sprint 6 - store-signed builds out of scope (no paid accounts); release APK + 7-day iOS build instead |
| Integration-readiness docs + Vertex/BAA runbook | ◻ Sprint 6 (Vertex code path already shipped) |
| Final summary report with the measured comprehension lift | ◻ Sprint 6 |

Sprint files: [sprint-5.md](sprint-5.md) · [sprint-6.md](sprint-6.md)
