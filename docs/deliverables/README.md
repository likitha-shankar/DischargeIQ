# DischargeIQ - Deliverables Index

Source of truth: **`docs/DischargeIQ_WorkPlan_v2.pdf`** (13 Jul 2026), the
accepted thirteen-week work plan. Task IDs, sprint boundaries, checkpoint
dates, and acceptance criteria in this folder all come from it. Program rules
(gates, awards, repository and data rules) come from
`docs/LOF_LABS_RULES.md`, which is binding.

Structure: **four sprints, each closing on a LABS checkpoint.** The program
began 1 Jul 2026; active build started the week of 8 Jul, which is where the
thirteen weeks are counted from.

| Sprint | Weeks | Checkpoint closes | Award | Focus |
|---|---|---|---|---|
| [1](sprint-1.md) ✅ | 1-2 | [Tue 21 Jul](checkpoint-1.md) | $500 | Mobile core on a real phone |
| [2](sprint-2.md) ◑ | 3-6 | [**Tue 18 Aug**](checkpoint-2.md) | $1,250 | Rewards, testers, media decision |
| [3](sprint-3.md) ◻ | 7-10 | [Tue 15 Sep](checkpoint-3.md) | $1,250 | Teach-back evidence, clinician dashboard |
| [4](sprint-4.md) ◻ | 11-13 | [Tue 6 Oct](checkpoint-4.md) | $2,000 | Accuracy verification, demo readiness |

Each checkpoint releases its award on acceptance of the deliverables, not on
the date alone. A missed gate gets written feedback and a one-week cure
window to fix only the flagged criteria; passing in the cure window still
earns the award.

Files here: `sprint-N.md` (build work and task status), `checkpoint-N.md`
(what LOF accepts), `tasks/task-X.Y.md` (per-task detail, written as tasks
complete).

> Earlier revisions of this folder used a six-sprint, four-"tranche" structure
> at weeks 0/4/8/12. That was neither the plan's vocabulary nor its calendar
> and has been removed. `LOF_LABS_RULES.md` says explicitly to ignore the word
> "tranche".

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
| `task-5.1-clinician-review` | Clinician review portal: 0-5 rubric, final-demo evidence | `a5f5f43` |

`git log --oneline` between two tags shows exactly what a sprint added.
Reverting would destroy later work; checkout/tags show history non-destructively.

## Testing corpus change (decision, July 30 2026)

The 50-document generated synthetic corpus has been replaced as the primary
testing corpus by **106 real de-identified discharge summaries from
MTSamples** (`test-data/mtsamples/`, built by
`scripts/build_mtsamples_corpus.py`).

Why: the synthetic documents were well-formed by construction, so they never
exercised what real discharge paperwork actually looks like. The MTSamples
documents are transcriptions of genuine dictated work with identifiers
removed - narrative prose, no section headers, missing discharge fields,
pediatric patients. They found two real defects within a day of being
introduced (inpatient-only drugs extracted as take-home medications; adult
second-person voice used for an infant's caregiver).

Practical notes:

- The corpus is **gitignored**. The content is third-party sourced and this
  repository is public, so it is rebuilt from the script rather than
  committed. This also satisfies the program rule against clinical or eval
  data sitting in a public repo.
- The synthetic corpus is **not lost**. It remains in the tags and the Neon
  `synthetic_corpus` table is untouched. Restore with
  `git checkout task-4.4-corpus-lock -- test-data/synthetic`.
- Three synthetic documents (`heart_failure_01`, `copd_01`,
  `hip_replacement_01`) stay committed at the top of `test-data/`: the beta
  kit ships them and `test_ingest.py` parses one.
- **Task 5.2 rubric resolved (July 30 2026).** Real documents are the point
  of the product, so the corpus stays real and the *rubric* was fixed instead.
  Measured across the 106 documents: warning signs appear in 34%, discharge
  medications in 62%, follow-up in 69%, activity or diet in 53%. The old
  anchors ("safe and complete", "dangerously incomplete") were absolute, so a
  reviewer would have penalised correct output for a section the source never
  contained - scoring the hospital's paperwork rather than this system. Every
  anchor in `ui/clinician_review.py` is now phrased relative to the source,
  and per-document guidance states the rule plainly: content absent from both
  source and output is not a penalty; content in the output but not the source
  is the serious failure. This keeps the gate measuring extraction fidelity,
  which is what a median of ≥ 4.0 is supposed to certify.

## Status at a glance (31 Jul 2026 - Week 4, mid Sprint 2)

| Item | Status |
|---|---|
| Sprint 1 / Checkpoint 1 | ✅ delivered |
| Sprint 2 / Checkpoint 2 (18 Aug) | ◑ build side met; **tester recruiting not started - the gating item** |
| Sprint 3 (15 Sep) | ◻ dashboard built early; full-corpus accuracy run outstanding |
| Sprint 4 (6 Oct) | ◻ adversarial audit already passed; clinician review blocked on LOF reviewers |

Work has run ahead of the plan in places: the teach-back loop, the clinician
dashboard, and the adversarial safety audit all landed before their sprints.
The items that are behind are the ones depending on other people - testers
and clinician reviewers - which is why they are worth raising early rather
than late.

## Testing corpus change (decision, July 30 2026)

The 50-document generated synthetic corpus has been replaced as the primary
testing corpus by **106 real de-identified discharge summaries from
MTSamples** (`test-data/mtsamples/`, built by
`scripts/build_mtsamples_corpus.py`).

Why: the synthetic documents were well-formed by construction, so they never
exercised what real discharge paperwork actually looks like. The MTSamples
documents are transcriptions of genuine dictated work with identifiers
removed - narrative prose, no section headers, missing discharge fields,
pediatric patients. They found two real defects within a day of being
introduced (inpatient-only drugs extracted as take-home medications; adult
second-person voice used for an infant's caregiver).

Practical notes:

- The corpus is **gitignored**. The content is third-party sourced and this
  repository is public, so it is rebuilt from the script rather than
  committed. This also satisfies the program rule against clinical or eval
  data sitting in a public repo.
- The synthetic corpus is **not lost**. It remains in the tags and the Neon
  `synthetic_corpus` table is untouched. Restore with
  `git checkout task-4.4-corpus-lock -- test-data/synthetic`.
- Three synthetic documents (`heart_failure_01`, `copd_01`,
  `hip_replacement_01`) stay committed at the top of `test-data/`: the beta
  kit ships them and `test_ingest.py` parses one.
- **Task 5.2 rubric resolved (July 30 2026).** Real documents are the point
  of the product, so the corpus stays real and the *rubric* was fixed instead.
  Measured across the 106 documents: warning signs appear in 34%, discharge
  medications in 62%, follow-up in 69%, activity or diet in 53%. The old
  anchors ("safe and complete", "dangerously incomplete") were absolute, so a
  reviewer would have penalised correct output for a section the source never
  contained - scoring the hospital's paperwork rather than this system. Every
  anchor in `ui/clinician_review.py` is now phrased relative to the source,
  and per-document guidance states the rule plainly: content absent from both
  source and output is not a penalty; content in the output but not the source
  is the serious failure. This keeps the gate measuring extraction fidelity,
  which is what a median of ≥ 4.0 is supposed to certify.

## Status at a glance (July 31, 2026 - Week 4)

| Level | Item | Status |
|---|---|---|
| Gate 1 | Concept approved (Wk 2, Jul 21) | ✅ plan v2 delivered |
| Sprint 1 | Cloud backend + extraction pipeline (1.1–1.6) | ✅ complete - Cloud Run live on Gemini (rev `dischargeiq-00003-pmg`, Jul 7) |
| Sprint 2 | Mobile bridge + OCR (2.1–2.5) | ◑ 2.2/2.3/2.5 done; 2.4 re-scoped to the no-spend path (7-day iOS provisioning + direct APK) |
| Sprint 3 | Teach-back loop (3.1–3.3) | ✅ built early, game layer at v3 (3.4 tuning awaits tester data) |
| Sprint 4 | NotebookLM media + corpus lock | ◑ 4.4 lock tooling ready; 4.1/4.2 scaffolding + NotebookLM source docs built - actual audio gen remains |
| Sprint 5 | Clinical validation | ◑ 5.1 portal built; **5.3 adversarial audit PASSED 31 Jul** (6/6, run on Anthropic, commit a17fcfa); 5.2 scoring waits on LOF reviewers |
| Sprint 6 | Final packaging | ◑ 6.3 integration-readiness docs + 6.5 media-fallback tests done; 6.2 Python deps locked (release builds on paid-hold) |

The teach-back loop (Sprint 3 core) was pulled forward because it is the
headline metric - comprehension lift from ~13% baseline to a measured 50–70%.

## No-spend distribution path (decision, July 30 2026)

Neither store account will be purchased this summer. The developer is a
student and the $99 Apple enrollment and $25 Play registration are not
funded. Per the research-before-spend ladder (work-plan review Flag 6), rung 1
(an LOF-shared Apple account) remains open if LOF offers one; absent that, the
project runs entirely on rung 2:

- **iOS (Tasks 2.4, 6.2):** free 7-day development provisioning, proven on a
  real iPhone. The app is rebuilt and reinstalled over USB when the profile
  expires (`flutter build ios --release` then
  `xcrun devicectl device install app --device <udid> <Runner.app>`). No
  TestFlight, so iOS testers must have the device in hand with the developer.
- **Android (Tasks 2.5, 6.2):** direct-install release APK plus the Android
  emulator for development. No Play Console, no Internal Testing track. The
  beta kit (`scripts/build_beta_kit.sh`) is the distribution mechanism.
- **Effect on the beta target:** the "10–20 active installs" figure is
  reachable on Android only. iOS coverage is limited to devices physically
  provisioned by the developer, and each one needs a reinstall every 7 days.
  State this explicitly at the checkpoint rather than letting it read as a
  missed target.

**Unblocked July 30:** the adversarial audit (Task 5.3) no longer waits on
quota. Billing is restored and the Cloud Run backend reports
`llm_provider: vertex`, which is the funded path the task required.

## Gate compliance (checked at EVERY gate)

| Rule | State |
|---|---|
| LICENSE at root, Apache-2.0 | ✅ |
| Dependency/license manifest current | ✅ `DEPENDENCIES.md` |
| No GPL/AGPL or network-copyleft | ✅ two weak-copyleft items documented |
| No synthetic/eval data in a PUBLIC repo | ✅ repo set **private** 31 Jul 2026 |
| Authoritative repo LOF-controlled | ❌ **PENDING** - still on the personal GitHub; needs LOF org access before a gate review |
