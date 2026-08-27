# Sprint 4 - Accuracy Verification and Demo Readiness (Weeks 11-13, closes Tue 6 Oct 2026) ◻

Task IDs follow `docs/DischargeIQ_WorkPlan_v2.pdf`. October delivers a
finished artifact, not the construction of one. Nothing is built after week 13.

**Checkpoint 4 accepted when:** the Sprint 4 dress rehearsal runs, all nine
steps; accuracy verified at the 98-100% bar on tested content; the
adversarial audit passes on tested cases; the clinician sample verification is
complete with every flag traced to a fix; the final summary report and the
backup recording are delivered.

| Task | Deliverable | Status |
|---|---|---|
| 4.1 | Adversarial safety audit on funded quota, with report | ✅ **PASSED 31 Jul 2026** - 6/6 cases, `a17fcfa`. Run on Anthropic (funded) because Vertex quota could not serve the suite. Found and fixed a real injection hole in Agent 1 first (`dc4f3ab`) |
| 4.2 | Clinician sample verification, 1-2 LOF reviewers, 5-10 documents | ◻ portal built `a5f5f43`; rubric corrected 31 Jul to judge fidelity to source. Liebovitz review received 22 Aug (`docs/LIEBOVITZ_REVIEW_RESPONSE.md`) and oversight options proposed (`docs/PHYSICIAN_OVERSIGHT_OPTIONS.md`, LOF action item 26 Aug). **Still blocked on LOF assigning reviewers - longest lead time in the plan** |
| 4.3 | Fix pass: every flagged item traced to the commit that closed it | ◻ depends on 4.2 |
| 4.4 | UI, UX, accessibility polish; re-verify media degradation after it | ◑ empty-section messages, density caps, person profiles, plus the **v2 redesign and an accessibility pass** (contrast, 2.2x text scaling, screen-reader headings) `5983841`. Final polish pass remains |
| 4.5 | Production builds with locked dependencies | ◑ Python locked (`requirements.lock.txt`); release APK builds. Store-signed builds are out of scope with no paid accounts |
| 4.6 | Integration-readiness documentation and Vertex/BAA runbook | ✅ `docs/INTEGRATION_READINESS.md` |
| 4.7 | Final summary report: accuracy, comprehension lift, telemetry, limitations | ◑ **draft written 16 Aug** `3661a04` - `docs/FINAL_SUMMARY_REPORT.md`. Still aggregates 4.2 (blocked) and the partial 3.4 run, so the figures are provisional |
| 4.8 | Tribune Tower demo package: rehearsed script, stable dataset, backup recording | ◑ live script `docs/DEMO_SCRIPT.md`, offline fallback `docs/demo_fallback.html`, backup-recording runbook `f861677`, and **external demo-video script `docs/DEMO_VIDEO_SCRIPT.md`** (LOF action item, 26 Aug). **Neither recording is made yet** |

## Note on 4.1

The audit passed only after two defects in the gate itself were fixed: it
reported GATE PASSED on a run where every LLM call had failed, and it scored
Agent 1's own defensive warning as a leak. Both are recorded in `a17fcfa`.
A gate that cannot fail is not evidence.
