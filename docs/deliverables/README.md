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

`git log --oneline` between two tags shows exactly what a sprint added.
Reverting would destroy later work; checkout/tags show history non-destructively.

## Status at a glance (July 5, 2026 - Week 2)

| Level | Item | Status |
|---|---|---|
| Tranche 1 | Mobilization (work plan) | ✅ plan v2 delivered |
| Sprint 1 | Cloud backend + extraction pipeline (1.1–1.6) | ✅ complete |
| Sprint 2 | Mobile bridge + OCR (2.1–2.5) | ◑ 2.2/2.3 done - store distribution (2.4/2.5) blocked on dev account |
| Sprint 3 | Teach-back loop (3.1–3.3) | ✅ built early (3.4 tuning awaits tester data) |
| Sprint 4 | NotebookLM media + corpus lock | ◻ corpus already generated; lock at Week 8 |
| Sprints 5–6 | Clinical validation + packaging | ◻ Month 3 |

The teach-back loop (Sprint 3 core) was pulled forward because it is the
headline metric - comprehension lift from ~13% baseline to a measured 50–70%.
