# DischargeIQ - LOF LABS Master Compliance & Status Document

**Prepared by:** Likitha Shankar (solo developer) · MS Computer Science, Illinois Institute of Technology
**Prepared for:** Leap of Faith, LLC - LOF AI Build Studio (LABS), Summer 2026
**Document date:** July 8, 2026 (Week 2)
**Sources reconciled:** LOF LABS Participant Guide (authoritative) + DischargeIQ Twelve-Week Work Plan

---

## 0. How to read this document

This is the single project-management source of truth. It does three things:

1. Restates **every requirement** in the LOF LABS Participant Guide and maps it to DischargeIQ's current state.
2. Reconciles the Participant Guide against the older Work Plan, which are on **different schedules** (see §1).
3. Gives a master **done / to-do** task register and a **gate-by-gate readiness** assessment.

Legend: ✅ done · ◑ partial (built, activation/data pending) · ◻ not started · ⏸ on paid-hold · 🚩 PM flag

---

## 1. ✅ RESOLVED - the calendar conflict is gone

This section used to flag a disagreement between the Participant Guide and the
work plan. **Work Plan v2 (13 Jul 2026) resolved it.** The flag described the
older 12-week draft, which used four "tranche" gates at weeks 0/4/8/12.

v2 is thirteen weeks in four sprints, and its checkpoints land exactly on the
Guide's gates:

| | Guide phase / gate | Work Plan v2 sprint | Date | Award |
|---|---|---|---|---|
| 1 | Gate 1, end Wk 2 | Sprint 1 (Wks 1-2) | Tue 21 Jul | $500 |
| 2 | Gate 2, end Wk 6 | Sprint 2 (Wks 3-6) | Tue 18 Aug | $1,250 |
| 3 | Gate 3, end Wk 10 | Sprint 3 (Wks 7-10) | Tue 15 Sep | $1,250 |
| 4 | Final demo, Wk 13 | Sprint 4 (Wks 11-13) | Tue 6 Oct | $2,000 |

The two documents now agree on duration, phase boundaries, gate timing, and
awards. The only remaining difference is vocabulary: the Guide says "gate",
the work plan says "checkpoint". They are the same event.

`docs/deliverables/` was realigned to this on 31 Jul 2026 - four sprints, four
checkpoints, task IDs taken from v2.

**Schedule risk remains low, but it has moved.** Build velocity is not the
problem; most of the plan is already built. The live risks are external
dependencies: tester recruiting for Checkpoint 2 (18 Aug) and clinician
reviewers for Checkpoint 4, neither of which is ours to schedule.

---

## 2. Program structure (from the Guide)

- **9 teams · 13 weeks · 4 phases · 3 pass/fail gates · final demo · up to $5,000/team.**
- Judged against a **fixed quality bar, not other teams.** No finalist cap. Every team that clears the gates continues.
- Rewards **concrete evidence**: running software, committed source, clear docs, verifiable demo.
- **One-week cure window** per failed gate; re-review covers only the flagged criteria; may work next phase in parallel at own risk.
- **Milestone awards are gated** (no clearance, no award), including after an approved cure window.

| Phase | Weeks | Gate | Award | Cumulative |
|---|---|---|---|---|
| 1 Ideation & team formation | 1-2 | Gate 1: Concept approved (end Wk 2) | $500 | $500 |
| 2 Prototype build | 3-6 | Gate 2: Working prototype (end Wk 6) | $1,250 | $1,750 |
| 3 Build & refine | 7-10 | Gate 3: Feature-complete beta (end Wk 10) | $1,250 | $3,000 |
| 4 Polish & rehearse | 11-13 | Final demo (Wk 13) | $2,000 | $5,000 |

---

## 3. Gate checklists - every box, with current status

### Gate 1: Concept approved - end of Week 2 (bar: clear thinking + commitment, NOT working software)

| # | Guide requirement | Status | Evidence / note |
|---|---|---|---|
| 1 | Problem stated clearly (who, why it matters) | ✅ | Work Plan §1; ~13% comprehension, 64% ER-instruction misunderstanding, CMS penalty framing |
| 2 | Proposed solution/approach described | ✅ | Standalone mobile-first 6-agent pipeline; Work Plan §1 + PROJECT_DEFINITION.md |
| 3 | All members named, roles assigned, availability confirmed | ✅ | Solo project - Likitha Shankar (backend, frontend, LLM, data) |
| 4 | Scope realistic for the timeline | ✅ | Work Plan §4 in/out-of-scope table; already building ahead |
| 5 | Defined "done" + how they'll know it works | ✅ | Work Plan §3 Definition of Success (7 measurable dimensions) |
| 6 | Repo under LOF control, LICENSE at root, third-party items identified | ◑ 🚩 | LICENSE ✅ (Apache-2.0); DEPENDENCIES.md ✅. **Repo still on personal GitHub - must migrate to LOF-controlled org (access pending).** |

**Gate 1 verdict: essentially clear except the one open item - the authoritative repo must be the LOF org.** Chase LOF for the org/access now.

### Gate 2: Working prototype - end of Week 6 (something must actually run)

| # | Guide requirement | Status | Evidence / note |
|---|---|---|---|
| 1 | Core function executes live, not described | ✅ | Cloud Run backend live; upload → 6-agent pipeline → JSON |
| 2 | ≥1 complete user path end to end | ✅ | Upload/scan → 7-tab plain-language result → teach-back quiz |
| 3 | Handles real/realistic input, not only hardcoded happy path | ✅ | 50-doc synthetic corpus; camera OCR path; `rejected` for wrong docs |
| 4 | Team can state what's NOT built + what's next | ✅ | This document, §6-§8 |
| 5 | Panel can verify live or via recording | ◑ | Live demo works; **backup recording still to cut** (Guide §9) |
| 6 | Repo, LICENSE, dependency manifest current | ◑ 🚩 | LICENSE + manifest current; repo-migration open (as Gate 1) |

**Gate 2 verdict: functionally already met in Week 2.** Outstanding: LOF repo migration + backup recording.

### Gate 3: Feature-complete beta - end of Week 10 (the main quality filter)

| # | Guide requirement | Status | Evidence / note |
|---|---|---|---|
| 1 | Every feature in approved scope present & functional | ◑ | Pipeline, mobile, quiz, dashboard, media scaffolding all built; NotebookLM audio files + clinician scoring outstanding |
| 2 | Runs full demo flow without crashing/blocking bugs | ✅ | Pipeline never crashes by contract; 92 backend tests green |
| 3 | Behaves reasonably on bad input / failure | ✅ | `rejected` status + screens; media fallback tests (Task 6.5); partial-status contract |
| 4 | A non-builder can complete the main task with minimal help | ◑ | Beta onboarding doc exists; needs a fresh-user run-through |
| 5 | Complete, substantive functionality; nothing core missing | ◑ | Core comprehension loop complete; media audio + clinical scores are the remaining "core" gaps |
| 6 | Repo, LICENSE, manifest current | ◑ 🚩 | as above |

**Gate 3 verdict: on track and ahead; blockers are the 5 NotebookLM audios, the 2 clinician reviewers, and repo migration.**

### Final demo - Week 13

- Completed project presentation + demonstration of finished work. Prep detailed in §9.

---

## 4. Repository, license & data compliance (Guide §7)

| Requirement | Status | Action |
|---|---|---|
| Milestone work in **LOF-controlled** repo (not personal) | 🚩 ◻ | **OPEN - highest-priority admin item.** Repo lives at personal GitHub; migrate to LOF org when access granted. Confirm privacy before pushing (synthetic corpus is committed). |
| Source, docs, issues, commits, deliverables in that repo | ◑ | All present; will move with repo migration |
| LICENSE at root, default **Apache-2.0** | ✅ | `LICENSE` = Apache-2.0 |
| Lightweight dependency/license manifest, kept current | ✅ | `DEPENDENCIES.md` regenerated 2026-07-07 |
| **No GPL / AGPL / network-copyleft** unless LOF+IIT approve in writing | ✅ | fpdf2 (LGPL) removed → reportlab (BSD); only transitive `pyphen` tri-license (used under LGPL/MPL option, no obligation) |
| **No clinical / synthetic / eval / restricted data in a PUBLIC repo** without written approval | 🚩 ◑ | Corpus is synthetic-only (safe content), but **repo must be confirmed private** or written approval obtained. Verify at migration. |

---

## 5. Reconciled 13-week calendar (Guide gates × Work Plan tasks)

| Guide week | Phase / Gate | Work Plan tasks landing here | Status |
|---|---|---|---|
| Wk 1-2 | Phase 1 → **Gate 1 (concept)** | Mobilization; Sprint 1 (1.1-1.6) already done; Sprint 3 core done | ✅ ahead |
| Wk 3-6 | Phase 2 → **Gate 2 (prototype)** | Sprint 2 mobile/OCR (2.2/2.3/2.5 done; 2.4 ⏸); Sprint 3 dashboard | ◑ ahead |
| Wk 7-10 | Phase 3 → **Gate 3 (beta)** | Sprint 4 media + corpus lock; Sprint 5 clinical validation | ◑ |
| Wk 11-13 | Phase 4 → **Final demo** | Sprint 6 polish + packaging | ◑ |

---

## 6. Master task register (Work Plan tasks × build state)

### ✅ Done
- **1.1** Infra + Neon connection pooling (lifespan pool, structured-only schema)
- **1.2** FastAPI on Cloud Run (nginx multiplex; Gemini redeploy rev `00003-pmg`)
- **1.3** Supervisor/router agent (gates non-discharge docs before Agent 1)
- **1.4** Model routing: Gemini primary + Claude failover + Vertex/BAA path + FK gate
- **1.5** 50-document synthetic corpus (generator + PDFs + index)
- **1.6** Corpus loaded to Neon (`synthetic_corpus`, 50 rows)
- **2.2 / 2.3** Camera scan + on-device ML Kit OCR + `POST /analyze/text`
- **2.5** Android beta APKs (arm64 30.9MB, ML Kit R8 fix, beta kit assembler)
- **3.1** Teach-back quiz backend (5 MCQ, pre/post delta, `quiz_scores`)
- **3.2** Gamified quiz UI both surfaces + game layers v2/v3 (XP, badges, mastery)
- **3.3** Streamlit clinician dashboard (read replica, deltas, flagged gaps)
- **3.4** Quiz-gap tooling (Streamlit-free analytics, evidence pipeline)
- **4.4** Corpus lock tooling (SHA-256 + `--verify` drift check)
- **5.1** Clinician review portal (0-5 rubric, gate math, `clinician_scores`)
- **6.3** Integration-readiness docs + Vertex/BAA runbook (`docs/INTEGRATION_READINESS.md`)
- **6.5** Media-fallback verification tests (3 failure modes, loop-alive assertions)
- Hardening: first-class `rejected` status + non-discharge screens both surfaces

### ◑ Partial (built; blocked on data/reviewers/manual step - NOT on money)
- **4.1** Media workflow: endpoints, players, per-diagnosis strategy done - **5 NotebookLM audio files not yet generated** (manual, ~1hr)
- **4.2** Media quality pass: NotebookLM **source docs built** (`media/sources/`, phonetic hints + bulleting) - actual audio generation + listen-through remains
- **5.2** Clinician scoring - portal ready; **awaits the two LOF-assigned reviewers**
- **5.3** Adversarial safety audit - suite built + runnable (`evaluation/adversarial_audit.py`); **last live run was vacuous (LLM quota exhausted) - needs a valid run under paid quota / Vertex**
- **5.4** Fix pass for <4.0 docs - depends on 5.2 scores
- **6.1** UI/UX polish - degradation paths shipped; final polish pass remains
- **4.7** Final summary report - aggregates the clinician review (4.2) and accuracy run (3.4)

### ◻ / ⏸ Not started or on paid-hold
- **2.1** Flutter scaffold/themes/state mgmt - largely subsumed by existing app; confirm/close
- **2.4** ⏸ iOS TestFlight - config ready; **blocked on $99 Apple Developer enrollment**
- **2.5 (Play)** ⏸ Google Play Internal Testing - deferred to first LOF payout (APK covers Android now)
- **4.3** ◻ Spanish support - explicit stretch; cut first if velocity slips
- **6.2** ◑/⏸ Production builds - Python deps locked (`requirements.lock.txt`); **release iOS/Android + Dart lock on paid-hold**

---

## 7. Paid-hold register (per instruction: hold paid items, ready everything else)

| Item | Task | Blocker | Interim coverage |
|---|---|---|---|
| iOS TestFlight | 2.4 | $99 Apple Developer enrollment | Android direct-install APK |
| Google Play Internal Testing | 2.5 | Play account / first payout | Direct-install APK |
| Release production builds | 6.2 | Depends on store accounts above | Python deps already locked |
| Valid adversarial audit run | 5.3 | Needs paid LLM quota or Vertex/BAA | Suite built; gate logic unit-verified |

**Everything not in this table has been built or is blocked only on a free action (reviewers, a manual audio-gen hour, or repo migration).**

---

## 8. Risk register (Work Plan §6, updated to current state)

| Risk | Severity | Current mitigation state |
|---|---|---|
| AI hallucination in med/diagnosis content | Critical | FK + safety gates from Sprint 1; hard-rule prompts; adversarial suite built (needs valid run); null-is-better-than-wrong enforced in code |
| Serverless DB connection exhaustion | High | Lifespan-scoped Neon pool shipped (Task 1.1) |
| NotebookLM media fragility | Moderate-high | Per-diagnosis manual model; app degrades silently to text; fallback tests green (6.5) |
| App-store review delay | Moderate | ⏸ paid-hold; direct-install APK is the interim path |
| Comprehension lift stalls below target | High | Baseline measured early; 3.4 tuning pipeline ready; awaits tester data |
| Solo-engineering bottleneck | Moderate | Sequential plan; far ahead of schedule; Spanish stretch is the first cut |
| 🚩 Repo not under LOF control | High (gate) | **OPEN** - every gate checks this; migrate ASAP |
| 🚩 Provider quota exhaustion (both providers dead Jul 8) | Medium | Move to paid Gemini tier or Vertex before any live demo/audit |

---

## 9. Demo preparation checklist (Guide §9)

- [ ] Demo script written - problem, user, workflow, core feature, evidence, limitations, next steps → **done: `docs/DEMO_SCRIPT.md`**
- [ ] Stable demo dataset fixed - **locked 50-doc synthetic corpus**; 3 named docs (heart_failure_01, a non-discharge PDF, copd_01)
- [ ] **Backup recording** of the full path - ◻ to cut (covers live-env failure)
- [ ] Show the core flow completely, not ten partial features - scripted
- [ ] Reviewer can see what changed since prior gate - git demo tags per task
- [ ] Handoff rehearsal - N/A (solo)

---

## 10. Communication cadence (Work Plan §8 + Guide §5)

- **Weekly status report:** 1-2 pages every Friday by noon - what shipped, what slipped, why.
- **Bi-weekly live demo:** functional software on a real device at the end of each sprint.
- **Surface blockers early** (Guide §2): current open blockers = LOF repo access, 2 clinician reviewers, $99 Apple enrollment, LLM quota.

---

## 11. Healthcare & AI expectations (Guide §8) - how DischargeIQ answers each

| Guide expectation | DischargeIQ answer |
|---|---|
| Define the intended user | Post-discharge patient (primary); care coordinator/clinician (secondary, dashboard) |
| Explain the workflow it belongs to | Hour-zero at home: scan/upload → plain-language + quiz; clinician reviews flagged gaps |
| Be clear what the AI does / does not do | Assist/summarize/educate/triage only; HITL notice in UI; never a clinical decision |
| Avoid unsupported clinical claims | Hard rules: no med-change advice; Agent 1 never fabricates; null over guess |
| Behave on incomplete/confusing/wrong input | `rejected` / `partial` / `complete_with_warnings` statuses; retry screens; never crashes |
| Use realistic data carefully, follow restrictions | Synthetic/de-identified only; no PHI stored; Vertex/BAA required before any real data |

---

## 12. PM action list - next moves, priority order

1. 🚩 **Chase LOF for the LOF-controlled repo/org** and migrate. This is checked at *every* gate and is the only open Gate-1 item.
2. **Confirm repo privacy** (synthetic corpus is committed) before any push.
3. **Generate the 5 NotebookLM audio files** from `media/sources/` (~1 hr, free) and run the listen-through (Task 4.2).
4. **Move LLM to paid Gemini tier or Vertex**, then re-run the adversarial audit for a valid Task 5.3 result.
5. **Cut the backup demo recording** (Gate 2/final requirement).
6. **Follow up with LOF on the two clinician reviewers** (unblocks 5.2 → 5.4 → 6.4).
7. Keep paid items (Apple enrollment, Play) parked until funding; APK covers Android.
8. Resume weekly Friday status reports + bi-weekly device demos.
