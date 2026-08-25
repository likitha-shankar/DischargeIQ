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

## 0b. If it 429s mid-demo - the offline fallback

**Open `docs/demo_fallback.html` in a browser. That is the whole procedure.**

No backend, no network, no API key, no terminal. It renders real pipeline
output captured earlier, with the same seven-tab layout in the same order, so
you can carry on talking through the identical material.

Why this exists rather than "hope it works": Vertex serves Gemini through
**dynamic shared quota**. There is no reserved capacity and no reset window,
so a 429 is possible at any moment and nothing you do the morning of the demo
prevents it. One analysis needs six calls in a row. Verified 25 Aug 2026: a
paced corpus run was losing roughly 40% of documents to 429s.

What to say if you switch to it, rather than going quiet:

> "That's the shared-capacity limit on the model provider's side, which is
>  exactly the failure mode the system is built to survive. Here's the same
>  document analysed a few minutes ago."

That is a better answer than a spinner, and it demonstrates the resilience
argument instead of describing it.

Rebuild it whenever the fixtures or prompts change:

```bash
python scripts/build_demo_fallback.py     # no API calls, instant
```

**It is a fallback, not a mock.** Every word came from a real run against the
committed fixture, and the page states its generation timestamp on its face.
Do not present it as live.

Currently included: `heart_failure_01` and `copd_01` - both documents the live
path below actually drives. The page lists anything missing rather than
quietly omitting it, so check the top of it before you present.

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

## 9. Recording the backup (task 4.8)

The backup recording exists for one job: if the venue network, the phone or
the backend fails at Tribune Tower, this plays instead. It does not need to be
polished. It needs to be COMPLETE and HONEST - a recording that skips the
rejected-document step is worthless precisely when you need it.

Record it while the system is verified green, not on the morning of the event.
State verified 16 Aug 2026: revision dischargeiq-00022-mdb, 9/9 guardrails,
phone build installed, iOS profile valid to ~22 Aug.

### Setup (5 minutes)

1. Connect the iPhone by cable and unlock it.
2. Open QuickTime Player, File > New Movie Recording, and pick the iPhone as
   both the camera and the microphone source. The phone screen becomes the
   video feed.
3. Silence notifications on the phone (Focus / Do Not Disturb). A message
   banner mid-recording means recording again.
4. Have the printed heart-failure summary ready if demonstrating the camera
   scan, and the invoice PDF reachable for step 4.
5. Run the pre-flight from section 0 immediately before recording.

### Shot list, with timings

| Time | Shot | Say |
|---|---|---|
| 0:00-0:30 | Home screen | The problem: discharge documents are written for the next clinician. ~13% full comprehension. |
| 0:30-1:15 | Scan or upload heart_failure_01 | What the patient does at hour zero, at home. |
| 1:15-1:35 | The disclaimer appears | Written by AI, not medical advice, cannot be dismissed by tapping away. Say this out loud - it is the HITL point Frank raised on 5 Aug. |
| 1:35-3:00 | Walk the seven tabs | On Warning signs: all three tiers open, and each symptom says WHY it matters. On Recovery: one card per week. |
| 3:00-4:15 | Teach-back loop | Baseline quiz, learning cards, post quiz, then the comprehension delta banner. The headline metric. |
| 4:15-4:45 | Upload the invoice | One honest "try another document" screen with a reason. No empty tabs, no crash. |
| 4:45-5:15 | Clinician dashboard | The session with its delta, and any post-quiz miss in the flagged-gaps list. |
| 5:15-5:45 | Limitations | Say them plainly, from section 7. Ending on limitations is what makes the rest credible. |

Six minutes total. Do not re-record for small stumbles - a human voice
correcting itself reads as honest; a polished demo reads as a sales pitch.

### After recording

- Store it OUTSIDE this repository (it shows real analysis output). The
  device-backups convention applies: gitignored, or better, off the laptop.
- Note in the deliverables that 4.8's recording exists and where it lives.
