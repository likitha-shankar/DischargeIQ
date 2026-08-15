# DischargeIQ - Demo Script

Follows the LOF Participant Guide section 9: problem, user, workflow, core
feature, evidence, limitations, next steps. Narrow, rehearsed, honest about
limits. A backup recording covers a live-environment failure.

## 0. Stable demo dataset

Use the **locked 50-document synthetic corpus** (`test-data/synthetic/`,
`corpus_lock.json`). For the live walkthrough, drive these three, in order:

| Document | Shows |
|---|---|
| `heart_failure_01.pdf` | Happy path - full 7-tab breakdown + teach-back lift |
| a plumbing-invoice / non-discharge PDF | `rejected` screen + retry (graceful bad input) |
| `copd_01.pdf` | Second diagnosis - proves it is not hardcoded to one |

Synthetic only - no real or program-provided patient data (LOF data rule).

## 1. Problem (30s)

Discharge documents are written for the next clinician, not the patient. Full
comprehension of discharge instructions is commonly cited at ~13%. Poor
understanding of return-to-ER instructions (the most misunderstood domain)
runs ~64%. Misunderstanding drives avoidable readmissions, which carry direct
CMS financial penalties for hospitals.

## 2. User (15s)

A patient who just got home from the hospital holding a document they cannot
read. Secondary user: a care coordinator / clinician who reviews flagged gaps.

## 3. Workflow (15s)

Hour zero, at home: scan or upload the discharge document -> get plain-language,
sixth-grade explanations across seven tabs -> take a before/after teach-back
quiz that measures whether comprehension actually improved.

## 4. Core feature demo (3-4 min) - the path shown live

1. **Upload** `heart_failure_01.pdf` (or scan on the phone app).
2. **Results** - walk the seven tabs in the order the app shows them: What
   happened, Medications, Appointments, Warning signs, Recovery, Test
   yourself, Discharge Check (gap score + missed concepts). The tab is
   labelled "Discharge Check" in the app, not "AI Review".
3. **Teach-back loop** - baseline quiz (no feedback) -> learning cards ->
   post quiz (feedback + explanations) -> **comprehension delta** banner.
   This is the headline metric: ~13% baseline -> measured 60-80% target.
4. **Graceful degradation** - upload the non-discharge PDF: one clean
   "try another document" screen, no empty tabs, no crash.
5. **Clinician dashboard** (port 8502) - the session appears with its delta;
   any post-quiz miss shows in the flagged-gaps list.

## 5. Evidence (inspectable, not described)

- **Running software:** Cloud Run backend live; Streamlit + Android release APK.
- **Comprehension lift:** stored quiz deltas in Neon (demo loop: 40% -> 100%, +60).
- **Readability gate:** every agent output FK-scored to `evaluation/fk_log.csv`.
- **Safety:** `evaluation/adversarial_audit.py` (prompt injection + corrupted
  input) and the hallucination gate `test_integration_hallucination.py`.
- **Corpus integrity:** `python scripts/lock_corpus.py --verify` (SHA-256 drift check).
- **Backup recording:** kept for the full path in case the live env fails.

## 6. Limitations (state them plainly)

- Media (NotebookLM audio/video) is per-diagnosis and generated manually; the
  5 files are not all produced yet. UI degrades silently to text when absent.
- iOS TestFlight build is config-ready but on hold pending the $99 Apple
  enrollment (paid item). Android ships as a direct-install APK.
- Clinician corpus scoring (median >=4.0 gate) awaits the two LOF reviewers.
- Adversarial audit must be re-run under real LLM quota / Vertex for a valid
  result (last run degraded on exhausted free-tier quota).
- Multi-instance PHI serving needs a shared session store (GCS/Redis) - not wired.

## 7. Next steps

- Generate the 5 NotebookLM audio files (sources ready in `dischargeiq/media/sources/`).
- Connect the two clinicians; complete the 50-document review.
- Re-run the adversarial audit under Vertex/paid quota; attach the report.
- Resume paid items (Apple enrollment -> TestFlight; Play Internal Testing).
