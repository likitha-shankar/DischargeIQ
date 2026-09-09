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

- The corpus is **committed** as of 14 Aug 2026. It was gitignored while this
  repository was public; the repo has been private since 31 Jul, and the
  program rule allows clinical and eval data in a private repo. All 106
  documents were scanned for SSNs, phone numbers, emails, MRNs and dates of
  birth before committing - zero hits. If the repo is ever made public, the
  corpus must come out of the working tree and out of history first.
- Generated synthetic documents are **no longer used for evaluation**. They
  remain in the tags and the Neon `synthetic_corpus` table is untouched;
  restore with `git checkout task-4.4-corpus-lock -- test-data/synthetic` if a
  comparison against well-formed documents is ever wanted.
- Three generated documents (`heart_failure_01`, `copd_01`,
  `hip_replacement_01`) stay committed at the top of `test-data/` as **demo
  and beta fixtures, not evaluation data**: the demo script drives them, the
  beta kit ships them, and `test_ingest.py` parses one. Handing a tester a
  real de-identified stranger's discharge summary to practise on is a
  different decision from evaluating against one.
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

## Status at a glance (25 Aug 2026 - Week 8)

Verified against the codebase on 25 Aug: every doc, script, tag and commit
SHA cited in this folder resolves. Nothing below is claimed without a file
or a commit behind it.

| Item | Status |
|---|---|
| Sprint 1 / Checkpoint 1 (21 Jul) | ✅ delivered |
| Sprint 2 / Checkpoint 2 (18 Aug) | ⚠ **date passed, outcome not recorded.** Build side met; 2.6 tester recruiting still marked not started. Cure window from 18 Aug expires 25 Aug |
| Sprint 3 (15 Sep) | ◑ dashboard built early; per-case audio ✅ done 16 Aug and wired into the app 6 Sep; accuracy run ✅ **complete on 106 of 106** (31 Aug), plus a 25-document degraded stratum (8 Sep). Only 3.5 remains, blocked on testers |
| Sprint 4 (6 Oct) | ◻ adversarial audit passed; final summary report drafted; clinician review still blocked on LOF reviewers |

Work has run ahead of the plan in places: the teach-back loop, the clinician
dashboard, and the adversarial safety audit all landed before their sprints.
The items that are behind are the ones depending on other people - testers
and clinician reviewers - which is why they are worth raising early rather
than late.

### The three things that need a decision, not more building

1. **Checkpoint 2's outcome is unrecorded.** See `checkpoint-2.md`.
2. **The 98-100% accuracy bar needs a definition.** Readability and
   medication fidelity clear it; numeric grounding does not yet. The choice
   of what gets certified is a Checkpoint 4 exposure. See `sprint-3.md`.
3. **The 3.4 corpus run is at 52% coverage and no longer advancing.** The
   nightly cron never worked and was disabled 25 Aug; Vertex dynamic shared
   quota means the throttling cannot be paced away or raised.

## Source-of-truth file is not in this repository

`docs/DischargeIQ_WorkPlan_v2.pdf` is cited throughout this folder as the
accepted plan that task IDs, sprint boundaries and acceptance criteria come
from. It is **gitignored** (`.gitignore:124`), has **never been committed**,
and is **not on disk**. Task IDs here can be checked against each other but
not against the plan they claim to derive from. If a gate review disputes a
task's scope, there is no artefact in this repository to point at. Consider
committing it, now that the repository is private.

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
