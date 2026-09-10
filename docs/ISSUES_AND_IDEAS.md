# DischargeIQ - Issues and Ideas Log

Internal tracking document (Work Plan v2, task 2.7), kept per John's guidance:
blockers and open questions to clear, plus ideas parked for later so nothing
is lost. For the developer's own clarity; available at reviews on request.
Newest entries first within each section.

## Open issues / blockers

| # | Issue | Status / next step |
|---|---|---|
| I-11 | No cross-document patient-identity guard. Each analysis is an independent session (fine), but (a) scan pages from DIFFERENT patients' documents can be combined in one scan session with no mismatch detection, and (b) game state (XP, stars, garden) is per-PHONE, so two people sharing a device share one garden. | Acceptable for the single-patient beta (no accounts by design, mirrors the privacy stance). Mitigations that exist today: "Start over" on the scan screen, per-document library entries. Real fix = caregiver profiles (P-6), out of summer scope. |
| I-10 | ~~Gemini free tier is 20 requests/day/model; ~2 runs/day before degradation.~~ **SUPERSEDED:** production runs on Vertex AI under the GCP project (BAA path), not the free tier, and no `GOOGLE_API_KEY` exists any more. The real constraint is different and cannot be raised: Vertex **dynamic shared quota** has no per-project limit, so 429s are capacity contention and no increase can be requested. Original text kept below. Fallbacks currently unfunded (Anthropic $0) or congested (OpenRouter :free upstream). | Demo-day risk #1. Fund one fallback (~$5-10) or move primary to paid tier before tester runs. Meanwhile: rehearse early on fresh quota; flip LLM_MODEL to gemini-2.5-flash for a second free bucket. |
| I-9 | Router degrades to document_type=unknown when its LLM call fails, so media matching would miss (text fallback covers it). Seen live July 11 under a Gemini 503. | Acceptable by design (never drop a real discharge). Revisit only if it shows up with funded quota. |
| I-8 | In-memory PDF/session stores are process-local; a Cloud Run scale-out or restart 404s /pdf/{session}. | Known limitation, documented. GCS/Redis shared store is the fix, deferred (not needed for beta scale, max-instances=1). |
| I-7 | iOS on-device delivery blocked on Apple access. | Research-before-spend order agreed: LOF shared account (ask Steve), free 7-day provisioning for demos, $99 only if LOF confirms. |
| I-6 | Two human-dependent items: 10 testers (Tanuj coordinating), repo arrangement with John (Bitbucket copy + license). | Chase in the next check-in. |
| I-5 | ~~Adversarial audit last ran vacuously - both providers exhausted, so injections never touched a live model.~~ | **RESOLVED 31 Jul 2026.** Re-ran on funded Anthropic quota: 6/6 passed, `a17fcfa`, and `evaluation/adversarial_audit.json` records `vacuous: false` with a real `pipeline_status` per case, so the injections did reach a live model. A real injection hole in Agent 1 was found and fixed first (`dc4f3ab`). This row stayed open until 9 Sep because nobody re-read the JSON. |
| I-4 | streamlit_app.py is ~6,000 lines (12x the repo's 500-line rule). New tabs already go in ui/. | Split during Sprint 6 polish, not before the demo. |
| I-2 | Backup demo recording (LOF guide section 9) not yet cut. | Record the first clean fresh-quota run - kills two birds. |
| I-1 | **Media quality pass still not done, and the gate it protects is now being crossed.** No generated audio has had a recorded human listen-through - not the five per-diagnosis NotebookLM WAVs, not the per-case TTS. Decision D-5 says `CASE_AUDIO_ENABLED` stays OFF until this approves the mechanism; it has been **`true` in production since Sep 2026** and the mobile client now calls `POST /media/case` on every What-Happened tab. Playback was confirmed working on device 8 Sep, which is a MECHANISM check, not a CONTENT review. | Do the listen-through before the beta kit goes to any tester - roughly 30 minutes for six files. Until then, audio reaching a tester breaches our own recorded gate. |

## Resolved (kept for the record)

| # | Issue | Resolution |
|---|---|---|
| I-3 | Calendar star (task 2.2) needs an add-to-calendar action, which does not exist yet. | Jul 11: add-to-calendar button on every appointment card (Google Calendar template link via url_launcher, no calendar permissions) + one-time `calendar_added` star. Star row is now 6 stars. |

## Decisions on record

| # | Decision | Why |
|---|---|---|
| D-7 | Enhanced cloud scan (`POST /analyze/image`): opt-in ONLY, explicit consent dialog, photos processed in memory and never stored server-side. Default scan path stays on-device ML Kit. | ML Kit cannot read handwriting; Gemini vision can. The photos-stay-on-phone rule is preserved as the default and broken only by the patient's explicit choice with plain-language disclosure. Synthetic/de-identified docs only until Vertex/BAA (same rule as the whole pipeline). (Jul 11.) |
| D-6 | On-device document library: successful analyses (result JSON + PDF) persist in the app's private storage; landing page lists them for instant reopen. Rejected docs not saved. | User decision Jul 11: closing the app must not lose the document. Device-local only - nothing new touches the server or DB, so the no-PHI-server-storage rule is untouched. Bonus: reopening burns zero pipeline quota. Privacy copy updated app-wide. |
| D-5 | Per-case TTS serving model: ON-DEMAND `POST /media/case` - client posts the pipeline payload it already holds, gets WAV bytes once, caches on device. Feature-flagged `CASE_AUDIO_ENABLED` (default off) until the 4.2 listen-through approves the mechanism. Rate-limited 4/min. | Pipeline-time pre-generation rejected: burns 2 model calls per upload under the 20/day quota (I-10) for audio most sessions never play, and adds latency to /analyze. Server-side session cache rejected: process-local store problem (I-8). Stateless POST matches the /chat and /quiz pattern, safe multi-instance, quota spent only when a patient presses play. (Jul 11.) |
| D-4 | Do NOT use notebooklm-py (or any reverse-engineered NotebookLM client) in the product. | Automates a consumer service against its ToS with personal account cookies; can break or cost the Google account any day; opposite of the comply-and-point compliance posture; the official Gemini TTS path already delivers per-case audio on our key. (Evaluated July 11 after it surfaced in research and again via community recommendation.) |
| D-3 | Per-case audio via Gemini TTS, not NotebookLM Enterprise. | Enterprise API needs a paid Gemini Enterprise license, is v1alpha audio-only, and 404s on our project. TTS is official, free-tier, proven hands-on (Task 1.12 findings). |
| D-2 | Clinician involvement = sampled verification with a checklist, not 50-document scoring. | July meeting: reviewers verify, they do not test; 50-doc scoring was rejected as unrealistic. |
| D-1 | 3D anatomy explainer removed from the tree. | Out of scope per the accepted work plan; kept privately as future material (trade-secret guidance). |

## Ideas parked for later (NOT current scope)

| # | Idea |
|---|---|
| P-5 | ~~Add-to-calendar deep link on Appointments tab (also unlocks the calendar star).~~ Shipped Jul 11 (see I-3). Native calendar write (device_calendar + permissions) stays parked if testers ask. |
| P-4 | Per-case VIDEO explainers if/when an official API path exists (no tier we can access has one today). |
| P-3 | Spanish support - explicit stretch, first cut (work plan 4.3). |
| P-2 | GCS/Redis shared session store for multi-instance PHI-grade serving. |
| P-1 | Caregiver share view - export the plain-language summary for a family member. |
| P-7 | On-device AI exploration (fall). Note on the "use Siri's Gemini" idea: the Apple-Google deal gives SIRI a custom Gemini on Apple's Private Cloud Compute - third-party apps get NO access to it. What apps DO get free is Apple's on-device Foundation Models framework (iOS 26, ~3B model). Realistic first step: move the grounded CHAT on-device via that framework; extraction/rewriting stays on the big-model pipeline. Device coverage rule: on-device AI needs recent chips (A17+/M-series) - the CLOUD pipeline stays the universal path, so old iPhones and phones without Siri/Apple Intelligence lose nothing; on-device is an upgrade, never a requirement. |
| P-6 | Caregiver profiles (multi-patient support on one phone): per-profile documents, quiz history, and garden; extraction patient_name consistency check across scan pages. TheraCareAI's dependent-profile model is the reference. Requires a data-model rethink - not before the fall. |

## Landing intro: two queued changes (25 Aug 2026)

Raised by Likitha: "why is there a button called 'watch intro again'? who
wants to watch the landing page?" Investigation found the button is the
smallest of three problems.

The intro is a **9.1 second branding animation** (`intro_screen.dart`): the
HELPING eyebrow, five rising phrase lines, a "Discharge" typewriter, an "IQ"
snap-in, then a fade. It teaches the user nothing. It is not a tutorial. The
genuinely useful walkthrough is the separate "Guided tour", which sits
directly above it in Settings and looks like its sibling.

**Done 25 Aug:** the intro now honours OS reduced motion and skips entirely.
See `test/intro_reduced_motion_test.dart`.

**Queued, deliberately held until after the 26 Aug demo:**

1. ~~**Remove "Watch the intro again" from Settings**~~ **DONE 10 Sep 2026.**
   Nobody replays a logo animation, and it invited confusion with "Guided
   tour" one row up, which is the thing a patient actually wants when they
   are lost. `test/settings_rows_test.dart` now asserts the row is absent and
   that the guided tour, licences and disclaimer rows survived.

   **Worth recording why this took two weeks.** The hold was for the 26 Aug
   demo. That demo passed, nothing was watching the queue, and the deferral
   outlived its reason until the row was noticed again in use. A queued item
   with a condition attached needs the condition rechecked, not the item
   remembered.

2. **Return the intro to once per install.** `main.dart` currently plays it on
   every cold launch by product decision, and the comment records that
   `SharedPreferences('intro_seen')` was deliberately removed to get that
   behaviour. For a demo audience the cinematic opener is an asset. For a
   patient who is unwell, tired or anxious and opening the app to check one
   dose, it is nine seconds of friction in front of their own medical
   information, every single time.

The tension is real and worth stating rather than resolving silently: the
demo audience and the patient want opposite things here. The proposal is to
keep the cinematic for a first launch, which is what a demo shows anyway, and
stop charging returning patients for it.