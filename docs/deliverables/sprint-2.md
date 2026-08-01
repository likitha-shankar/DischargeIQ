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
| 2.3 | Gamification strategy document (one page, honest claims) | ✅ `docs/GAMIFICATION_STRATEGY.md` rewritten 31 Jul: one-page summary up front, per-step patient walkthrough, build status matching what ships, garden/companion recorded as retired rather than described as live |
| 2.4 | NotebookLM hands-on API evaluation and findings report | ✅ `docs/NOTEBOOKLM_FINDINGS.md` - decision D-3: Enterprise API is licence-gated and 404s on our project, so per-case audio ships via Gemini TTS on our own key |
| 2.5 | iOS access findings, reported before any spend | ✅ `docs/IOS_ACCESS_FINDINGS.md` (1 Aug). Rung (b) free 7-day provisioning PROVEN on a real iPhone, expiry measured at exactly 7 days. Rung (a) LOF shared account **still unasked - the one open item**. No spend requested |
| 2.6 | Tester onboarding: up to 10 testers, sessions visible in the backend log | ❌ **NOT STARTED - the gating item for this checkpoint** |
| 2.7 | Issues-and-ideas list, maintained throughout | ✅ `docs/ISSUES_AND_IDEAS.md` |

## Demo-day note

The iOS provisioning profile in hand expires **6 Aug 2026**. Any iOS demo at
Checkpoint 2 on 18 Aug needs a rebuild on or after 11 Aug. See
`docs/IOS_ACCESS_FINDINGS.md`.

## Risk to Checkpoint 2

**The tester cohort has to be Android.** Without a paid Apple account there
is no TestFlight, so an iPhone tester cannot install the app themselves.

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
