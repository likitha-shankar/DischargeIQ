# DischargeIQ - Deliverables Index

Maps every work-plan deliverable to the commits that built it, at three levels:

- **Per tranche gate** - `tranche-N-*.md` (funding gates, what LOF accepts)
- **Per sprint** - `sprint-N.md` (bi-weekly demo units)
- **Per task** - `tasks/task-X.Y.md` (work-plan task IDs; written when a task completes)

## Showing the build progression (do NOT `git revert`)

Every milestone state is a tag. To demo the repo as it stood at any point:

```bash
git checkout <tag>      # look around, run the demo
git checkout main       # come back - nothing is lost
```

| Tag | State shown | Commit |
|---|---|---|
| `task-1.3-router` | Router agent gating the pipeline | `220c118` |
| `task-1.4-failover-vertex` | Claude failover + Vertex AI (BAA) path | `b2e07b2` |
| `task-1.5-corpus` | 50-document locked synthetic corpus | `ddad5bb` |
| `sprint-1-complete` | All of Sprint 1 (tasks 1.1–1.6) | `b8d2cdf` |
| `task-2.2-camera-ocr` | Camera scan + on-device ML Kit OCR (tasks 2.2/2.3) | `7a2bf9c` |
| `task-3.1-quiz-backend` | Teach-back quiz engine + API | `7efc3b7` |
| `task-3.2-quiz-mobile` | Gamified quiz in the Flutter app | `a7359fc` |
| `task-3.2-quiz-web` | Quiz tab on the Streamlit fallback | `de6d126` |
| `task-3.3-clinician-dashboard` | Clinician dashboard (deltas, flagged gaps) | `d86fc3c` |
| `task-3.4-gap-tooling` | Quiz-gap report: prompt-tuning evidence pipeline | `aef022a` |
| `task-3.2-game-v3` | Quiz game v3: Master-it rounds, XP/levels, badges, bests | `a0b4dbe` |
| `hardening-rejected-docs` | Non-discharge docs: `rejected` status + dedicated screens | `5d66d52` |
| `task-2.5-android-apk` | Android SDK + release APKs (arm64 30.9MB), ML Kit R8 fix | `61ac8af` |
| `task-5.1-clinician-review` | Clinician review portal: 0-5 rubric, Tranche 4 gate | `a5f5f43` |

`git log --oneline` between two tags shows exactly what a sprint added.
Reverting would destroy later work; checkout/tags show history non-destructively.

## Status at a glance (July 8, 2026 - Week 2)

| Level | Item | Status |
|---|---|---|
| Tranche 1 | Mobilization (work plan) | ✅ plan v2 delivered |
| Sprint 1 | Cloud backend + extraction pipeline (1.1–1.6) | ✅ complete - Cloud Run live on Gemini (rev `dischargeiq-00003-pmg`, Jul 7) |
| Sprint 2 | Mobile bridge + OCR (2.1–2.5) | ◑ 2.2/2.3/2.5 done (release APKs built) - 2.4 TestFlight on paid-hold ($99 Apple enrollment) |
| Sprint 3 | Teach-back loop (3.1–3.3) | ✅ built early, game layer at v3 (3.4 tuning awaits tester data) |
| Sprint 4 | NotebookLM media + corpus lock | ◑ 4.4 lock tooling ready; 4.1/4.2 scaffolding + NotebookLM source docs built - actual audio gen remains |
| Sprint 5 | Clinical validation | ◑ 5.1 portal + 5.3 adversarial suite built - 5.2 scoring waits on LOF reviewers; 5.3 needs a valid live run |
| Sprint 6 | Final packaging | ◑ 6.3 integration-readiness docs + 6.5 media-fallback tests done; 6.2 Python deps locked (release builds on paid-hold) |

The teach-back loop (Sprint 3 core) was pulled forward because it is the
headline metric - comprehension lift from ~13% baseline to a measured 50–70%.

## Paid-hold list (features built, activation deferred until payment)

Per the July 2026 instruction to hold paid items while getting features ready:

- **iOS TestFlight (Task 2.4):** config TestFlight-ready; blocked on the $99
  Apple Developer enrollment. Android ships as a direct-install APK meanwhile.
- **Google Play Internal Testing (Task 2.5):** deferred to first LOF payout;
  direct-install APK covers Android beta now.
- **Release iOS/Android production builds (Task 6.2):** depend on the store
  accounts above. Python backend deps are locked (`requirements.lock.txt`).
- **Adversarial audit valid run (Task 5.3):** suite runnable; a clean result
  needs real LLM quota (paid tier) or the Vertex/BAA path.
