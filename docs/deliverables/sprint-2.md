# Sprint 2 - Rewards, Testers, and the Media Decision (Weeks 3-6, closes Tue 18 Aug 2026) ◑ CURRENT

Task IDs follow `docs/DischargeIQ_WorkPlan_v2.pdf`.

**Checkpoint 2 accepted when:** the Sprint 2 demo runs live, all seven steps;
up to 10 testers are onboarded with sessions in the backend log; the
NotebookLM findings report, the iOS access findings report, and the
gamification strategy document are delivered.

| Task | Deliverable | Status |
|---|---|---|
| 2.1 | Teach-back quiz loop: frozen questions, no-feedback baseline, server-side delta | ✅ `7efc3b7`, `a7359fc`, `de6d126` - live delta verified 5 Jul (pre 40% → post 100%) |
| 2.2 | Rewards layer: stars per section, calendar action, levels, no timers | ✅ built, journey theme at v3 |
| 2.3 | Gamification strategy document (one page, honest claims) | ◑ `docs/GAMIFICATION_STRATEGY.md` exists but is STALE - it still describes the deleted garden/companion features. Rewrite before the checkpoint |
| 2.4 | NotebookLM hands-on API evaluation and findings report | ✅ `docs/NOTEBOOKLM_FINDINGS.md` - decision D-3: Enterprise API is licence-gated and 404s on our project, so per-case audio ships via Gemini TTS on our own key |
| 2.5 | iOS access findings, reported before any spend | ◑ ladder resolved in practice: rung 2 (free 7-day provisioning) proven on a real iPhone 31 Jul. Rung 1 (LOF shared Apple account via Steve/Chandan) NOT yet asked. **The written findings report to John and Tanuj is still outstanding** |
| 2.6 | Tester onboarding: up to 10 testers, sessions visible in the backend log | ❌ **NOT STARTED - the gating item for this checkpoint** |
| 2.7 | Issues-and-ideas list, maintained throughout | ✅ `docs/ISSUES_AND_IDEAS.md` |

## Risk to Checkpoint 2

Acceptance names testers explicitly, and demo step 5 opens "the log of real
tester sessions: how many people used it, their deltas, and which of the five
domains they failed most". That log cannot exist without recruits, and Tanuj
coordinates LOF-internal recruiting, so the lead time is not ours to control.

The beta kit is ready and passes its own backend health check
(`scripts/build_beta_kit.sh`). What is missing is people. This is the item to
raise first, ahead of any further feature work.

## Ready but not required here

Work that has landed early and belongs to later checkpoints: the adversarial
safety audit (task 4.1) passed on 31 Jul, and the clinician review portal
(task 4.2's instrument) is built.
