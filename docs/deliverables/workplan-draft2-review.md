# Work Plan draft2 - review flags and paste-ready fixes

## Flag 0 - ALL CHECKPOINT DATES (biggest fix; affects Sections 3, 6, 8)

Week 1 was spent producing the work plan; the week of July 20 is the first
demo week. Every "closes Tuesday" date in the draft is therefore one week
early. Corrected Tuesdays:

| Sprint | Draft says | Should say |
|---|---|---|
| Sprint 1 close / Checkpoint 1 | Tuesday, July 14 | Tuesday, July 21 |
| Sprint 2 close / Checkpoint 2 | Tuesday, August 11 | Tuesday, August 18 |
| Sprint 3 close / Checkpoint 3 | Tuesday, September 8 | Tuesday, September 15 |
| Sprint 4 close / Checkpoint 4 | Tuesday, September 29 | Tuesday, October 6 |

Note for John: Oct 6 runs one week past a strict July-1-plus-13-weeks count.
Either state that week 1 was mobilization (recommended - it is true), or
compress Sprint 4 to two weeks (Sep 15 → Sep 29). Decide once, apply
everywhere: the sprint-overview table (Section 3), each sprint heading in
Section 6, and the checkpoint table (Section 8).

Review of `DischargeIQ_WorkPlan_draft2.docx` (Jul 13 draft) against the
accepted v2 plan, the decisions on record (docs/ISSUES_AND_IDEAS.md), and the
actual build state. Each flag has replacement text ready to paste into the
Google Doc.

## Flag 1 - Risk register, hallucination row (MUST FIX - inaccurate claim)

Draft says the mitigation is "All inference via Vertex AI under BAA". Summer
inference runs on the Gemini API over synthetic data; Vertex is the built and
smoke-tested path REQUIRED before any real patient data, and the BAA is not
yet signed. Vertex is also a privacy control, not a hallucination control.

**Replace the Mitigation cell with:**
> Null-is-better-than-wrong enforced as code, not prompt text; automated
> hallucination gate (output-to-source diffing); adversarial injection suite;
> clinician sample verification. All real-data inference (future) runs on
> Vertex AI under BAA.

## Flag 2 - "Sprint 5's fix pass" (dead reference)

There is no Sprint 5. **Replace with:** "Extend tuning into Sprint 4's fix pass".

## Flag 3 - Missing Clinician Verification Plan section

Definition of Success cites "the one-page checklist in Section 8", but the
section was dropped. Reinstate v2's Section 8 (sampled verification, nurse or
discharge coordinator preferred, 5-10 documents, 10-15 minutes each, portal
with 0-5 score + hallucination flag, backup if reviewers are delayed). This
section answers the July meeting's redesign; its absence reopens a settled
question.

## Flag 4 - NotebookLM references are behind the decisions on record

D-3 (Jul 11): per-case audio ships via Gemini TTS on our own key; NotebookLM
Enterprise API is inaccessible (v1alpha, license-gated, 404s on our project);
reverse-engineered clients rejected (D-4); per-case VIDEO parked - no official
API path exists (P-4). The findings report (Task 1.12) is already delivered.

- Scope table: "Per-diagnosis or per-case audio explainers via text-to-audio
  (Gemini TTS), with NotebookLM evaluated hands-on and set aside per the
  findings report; the media component stays swappable."
- Tier 3: "Audio explainers (enhancement only; text-only teach-back is the
  primary validated workflow; no success metric depends on media)."
- Risk row title: "Media generation fragility" - mitigation: "Media is a
  swappable component behind a validated endpoint; per-diagnosis files and
  per-case TTS both degrade silently to the text-only loop (three failure
  modes already covered by automated tests)."
- Checkpoint 3: change "audio or video explainer" to "audio explainer", and
  "Delete the video file from the server" to "Disable the audio component on
  the server and run the same flow again."

## Flag 5 - Checkpoint 1: "The photo is never sent anywhere"

No longer an absolute: the opt-in enhanced handwriting reader (explicit
consent dialog) uploads page photos for cloud transcription.

**Replace with:** "The photo never leaves the phone on the standard scan.
One clearly labeled option - the enhanced reader for handwritten pages -
uploads photos only after the patient explicitly agrees on screen."

## Flag 6 - App store risk row is stale

**Replace mitigation with:** "iOS access follows the agreed
research-before-spend ladder: LOF shared account (Steve/Chandan), then free
7-day development provisioning (already proven on a real iPhone), then the
$99 enrollment only if LOF confirms. Android direct-install APK fully covers
beta testing meanwhile."

## Flag 7 - Reinstate two dropped v2 sections

- Data Flow and Safety (the 7-step document walk + how clinical advice is
  prevented in code + the two data modes). The LOF feedback report asked for
  this explicitly.
- Repository and Licensing (Apache-2.0, manifest, no copyleft, private repo,
  traceable milestones).

## Flag 8 - Fill the empty "Developing" cells

**Sprint 1 Developing:**
> 1.1 Cloud infrastructure: serverless Postgres with pooled connections that
> survive autoscaling; schema restricted to structured metadata and hashes.
> 1.2 Containerized FastAPI backend on Cloud Run serving analysis, chat,
> quiz, media, and progress endpoints. 1.3 Multi-agent pipeline: router gate
> rejects non-discharge documents before any downstream work; specialized
> agents for extraction, diagnosis, medications, recovery, warning signs,
> quiz generation. 1.4 Model routing: Gemini primary, automatic cross-provider
> failover, Flesch-Kincaid gate on every output; Vertex AI (BAA) path built
> for future real-data use. 1.5 Synthetic corpus: 50 de-identified documents,
> seeded generator, SHA-256 version locking. 1.6 Corpus metadata loaded to
> the database as the testing matrix. 1.7 Camera scan with on-device OCR,
> multi-page, retake guidance, add-pages loop. 1.8 Grounded chatbot on
> mobile with the same guardrails as web. 1.9 Android beta kit (APK, guide,
> samples, manifest).

**Sprint 2 Developing:**
> 2.1 Rewards layer over the discharge process: reading stars, calendar
> action star, XP, levels, mastery badges, recovery garden, first-week-home
> quests, daily gentle check-in - no timers, no streak punishment. 2.2
> Gamification strategy document (evidence-based, honest claims). 2.3
> Hands-on NotebookLM API evaluation and findings report deciding the media
> approach. 2.4 iOS access findings (research-before-spend ladder). 2.5
> Tester onboarding with the beta kit; sessions visible in the backend log.
> 2.6 Accessibility layer: read-aloud on every section, app-wide text size,
> caregiver share.

**Sprint 3 Developing:**
> 3.1 Teach-back evidence: measured comprehension deltas from the tester
> group; prompt tuning driven by the domains testers miss, with before/after
> scores on affected documents. 3.2 Clinician dashboard live with the
> random-sample review queue. 3.3 Media path executed per the findings
> (per-case Gemini TTS behind the validated endpoint), text-only fallback
> proven on three forced failure modes. 3.4 Full 50-document automated
> accuracy run: output-to-source diffing, readability log, chat grounding.

**Sprint 4 Developing:**
> 4.1 Adversarial safety audit on funded quota: prompt injection, dosage
> forcing, fabricated diagnoses, corrupted inputs - reject or null, never a
> confident wrong answer. 4.2 Clinician sample verification via the review
> portal; fix pass tracing every flagged item to its change. 4.3 Production
> builds with locked dependencies (Python and Dart locks already in place).
> 4.4 Final summary report with limitations; rehearsed and recorded demo.

## Flag 9 - Two word-level fixes

- Head start: "version-locked" → "version-locking in place; formal lock at
  Week 8" (the lock re-runs when the corpus freezes).
- Success table: "a verified 50-70%" → "a measured 50-70%" (v2 wording;
  "verified" implies clinician sign-off the metric does not carry).

## Also true but fine to leave

Checkpoint demo scripts are strong and everything they demand already exists
in the app today (blurred-page retake, grounded refusals, router rejection,
adversarial fixtures, backup-recording plan) except the two quota-gated runs
(50-doc sweep, valid adversarial run) already queued for a funded day.
