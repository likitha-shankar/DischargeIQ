# Task 2.6 - Tester Onboarding ❌ NOT STARTED

**Deliverable:** up to 10 testers onboarded, with their sessions visible in
the backend log.

**Status: not started. No testers recruited, no real sessions in the log.**
This is the single largest hole in the Gate 3 evidence package and it has
been the gating item since Checkpoint 2.

## The blocker is people, not software

Everything downstream is built and idle:

| Piece | State |
|---|---|
| Android beta kit, direct-install APK | ✅ `scripts/build_beta_kit.sh` |
| Backend session logging | ✅ `discharge_history`, `quiz_scores` |
| Clinician dashboard showing sessions and deltas | ✅ `ui/clinician_dashboard.py` |
| Per-domain gap report for prompt tuning | ✅ `evaluation/quiz_gap_report.py` |
| Onboarding instructions | ✅ `docs/beta/ONBOARDING.md` |

## What it blocks

- **Task 3.5** - prompt tuning against the domains real testers failed.
- **Liebovitz 2.1** - validate readability with teach-back in 10-15 patients.
- **Liebovitz 3.6** - report Agent 6 agreement with human teach-back.
- The comprehension-lift claim itself. The 13% → 50-70% target is a target
  with no measurement behind it until this runs.

## Scope note

The LOF review of 26 Aug 2026 set the shape: **10-15 patients, focused on
task completion and comprehension, NOT a large quantitative trial.** That is
a smaller ask than the original plan implies and worth saying to anyone who
thinks this needs a study protocol.

Tanuj is coordinating recruitment.

## One thing fixed here on 8 Sep 2026

The beta kit was packaging an APK built without the API key, which returns
**401 on every analysis** - a tester following the documented steps would
have seen an app that appears completely broken while the backend was
healthy. `docs/beta/ONBOARDING.md` had said no `--dart-define` was needed
since 14 August, the day before the key gate landed. Fixed in `a15c9f6`;
the kit now compiles the key in and refuses to build without it.

Worth knowing because it means any APK shared before 8 Sep 2026 was broken.
