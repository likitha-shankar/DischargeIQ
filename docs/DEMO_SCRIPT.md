# DischargeIQ - Demo Script

Follows the LOF Participant Guide section 9: problem, user, workflow, core
feature, evidence, limitations, next steps. Narrow, rehearsed, honest about
limits.

Last fact-checked against the running system: 16 Aug 2026, revision
`dischargeiq-00018-ww4`.

## 0. Before you present (run these, do not assume)

```bash
python scripts/verify_live_service.py --guardrails   # ~5s, spends nothing
```

That confirms the service is awake, the spend gate holds, and the API surface
is closed. Run it on the morning of the demo. The full run
(`python scripts/verify_live_service.py`, no flag) walks the entire patient
path and costs about fifteen LLM calls - worth doing the day before, not an
hour before.

Then check, in order:

- [ ] Cloud Run is serving the revision you expect
      (`gcloud run services describe dischargeiq --project dischargeiq-502723
      --region us-central1 --format='value(status.latestReadyRevisionName)'`)
- [ ] The phone build has not expired. Free iOS provisioning lasts **7 days**;
      rebuild with `./scripts/deploy_ios.sh <udid>` if in doubt. The rebuild
      takes about three minutes and preserves saved documents.
- [ ] The phone is unlocked, connected, and on a network that reaches the
      backend
- [ ] Vertex quota is not exhausted from a corpus run - a demo analysis needs
      six calls in a row, and a paced corpus job will starve it

**Never deploy on the day.** A revision change returned 502 for roughly three
minutes on 5 Aug.

## 1. Stable demo dataset

Three committed fixtures, in this order. These are **generated** documents
kept as demo and beta fixtures - the evaluation corpus is 106 real
de-identified summaries, which is a different thing and is described in
section 5.

| Document | Shows |
|---|---|
| `test-data/heart_failure_01.pdf` | Happy path: full seven-tab breakdown and teach-back lift |
| `test-data/not_a_discharge_invoice.pdf` | The `rejected` screen and retry, on obviously bad input |
| `test-data/copd_01.pdf` | A second diagnosis, proving it is not hardcoded to one |

No real or program-provided patient data is shown on screen (LOF data rule).

## 2. Problem (30s)

Discharge documents are written for the next clinician, not the patient. Full
comprehension of discharge instructions is commonly cited at ~13%. Poor
understanding of return-to-ER instructions, the most misunderstood domain,
runs ~64%. Misunderstanding drives avoidable readmissions, which carry direct
CMS financial penalties for hospitals.

## 3. User (15s)

A patient who just got home from the hospital holding a document they cannot
read. Secondary user: a care coordinator or clinician who reviews flagged
gaps.

## 4. Workflow (15s)

Hour zero, at home: scan or upload the discharge document, get plain-language
explanations across seven tabs at a sixth-grade reading level, then take a
before-and-after teach-back quiz that measures whether comprehension actually
improved.

## 5. Core feature demo (3-4 min) - the path shown live

1. **Upload** `heart_failure_01.pdf`, or scan a printed copy on the phone.
2. **The disclaimer appears first** and has to be acknowledged: written by AI,
   not medical advice, never change a medicine because of it, call 911 in an
   emergency. Say out loud that it cannot be dismissed by tapping away - this
   is the HITL framing Frank asked for on 5 Aug, and it is the first thing a
   patient meets.
3. **Results** - walk the seven tabs in the order the app shows them: What
   happened, Medications, Appointments, Warning signs, Recovery, Test
   yourself, Discharge Check. The last tab carries the gap score and the
   missed concepts; it is labelled "Discharge Check" in the app, never
   "AI Review".
   - On **Warning signs**, point out that all three tiers are open and that
     each symptom says why it matters, not just its name.
   - On **Recovery**, point out one card per week.
4. **Teach-back loop** - baseline quiz with no feedback, then learning cards,
   then the post quiz with feedback and explanations, ending on the
   **comprehension delta** banner. This is the headline metric: ~13% baseline
   against a measured 60-80% target.
5. **Graceful degradation** - upload `not_a_discharge_invoice.pdf`: one clean
   "try another document" screen with a reason, no empty tabs, no crash.
6. **Clinician dashboard** - `streamlit run ui/clinician_dashboard.py
   --server.port 8502`. The session appears with its delta, and any post-quiz
   miss shows in the flagged-gaps list.

## 6. Evidence (inspectable, not described)

- **Running software:** Cloud Run backend live; Streamlit and a signed Android
  release APK.
- **Readability, measured:** across the de-identified corpus, agent outputs
  are scored against a sixth-grade target and logged to
  `evaluation/fk_log.csv`. Every section of a single live analysis currently
  scores under target: diagnosis 3.1, medicines 3.8, recovery 4.4, warning
  signs 4.3.
- **Comprehension lift:** stored quiz deltas in Neon; a live loop scores 0%
  before and 100% after, with the delta computed server-side rather than by
  the app.
- **End-to-end verification:** `python scripts/verify_live_service.py` runs 28
  checks against the deployed service, including that one patient's session
  cannot be read from another's.
- **Safety:** `evaluation/adversarial_audit.py` passed 6 of 6 on 31 Jul 2026
  (prompt injection and corrupted input), after finding and fixing a real
  injection hole in Agent 1.
- **Corpus integrity:** `python scripts/lock_corpus.py --verify` (SHA-256
  drift check).

## 7. Limitations (state them plainly)

- **No backup recording exists yet.** If the live environment fails there is
  no fallback, so the pre-flight checks in section 0 are the mitigation.
- Per-case audio generates through Gemini TTS on the existing key; no audio
  files are pre-generated, and the UI degrades silently to text when absent.
- **No TestFlight build**, because that needs a paid Apple account this
  project does not have. iOS runs on free 7-day provisioning and needs the
  device in hand; Android ships as a direct-install signed APK.
- Clinician corpus scoring (median >= 4.0 gate) awaits the LOF reviewers.
- Multi-instance serving needs a shared session store (GCS or Redis) and is
  not wired. The service is pinned to a single instance, which is why "view
  original document" cannot land on an instance that never saw the upload.

## 8. Next steps

- Onboard the tester cohort and collect real comprehension deltas.
- Record the backup demo while the app is in a known-good state.
- Connect the clinicians and complete the sample review.
- Settle the repository handover and the Apple account question with LOF.
