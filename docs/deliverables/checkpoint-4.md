# Checkpoint 4 - Week 13, Tue 6 Oct 2026 - $2,000 ◻

**Accepted when:** the Sprint 4 dress rehearsal runs, all nine steps.
Accuracy verified at the 98-100% bar on tested content. The adversarial
audit passes on tested cases. The clinician sample verification is complete
with every flag traced to a fix. The final summary report and the backup
recording are delivered.

Program milestone: final demo, Tribune Tower. October delivers a finished
artifact, not the construction of one.

| Piece | Status |
|---|---|
| Adversarial audit passes on tested cases | ✅ 6/6 on 31 Jul, `a17fcfa` |
| Clinician sample verification, every flag traced to a fix | ◻ **blocked on LOF assigning reviewers** |
| Accuracy at the 98-100% bar on tested content | ◑ **met on readability (98% of 424 outputs, mean grade 4.08) and on medication fidelity (0 invented names across 106).** Numeric grounding was 25/106 outputs carrying a number absent from source; a deterministic post-generation guard now strips ungrounded clinical thresholds (`d4f64e5`, 26 of 212 sections rewritten, 0 grounded thresholds touched). Re-measure after the next corpus run before certifying. Say which bar is being certified |
| Production builds with locked dependencies | ◑ Python locked; store-signed builds out of scope |
| Integration-readiness documentation | ✅ `docs/INTEGRATION_READINESS.md` |
| Final summary report with limitations | ◑ draft `docs/FINAL_SUMMARY_REPORT.md` `3661a04`; figures provisional pending 4.2 and full 3.4 |
| Rehearsed demo and backup recording | ◑ script and runbook written `f861677`; recording not made. Four failure paths are now demonstrable - rejected document, missing media, degraded database, degraded source - and `scripts/dry_run.py` exercises 37 live checks in one command |

Sprint file: [sprint-4.md](sprint-4.md) ◻
