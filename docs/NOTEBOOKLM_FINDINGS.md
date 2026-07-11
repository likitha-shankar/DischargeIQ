# NotebookLM Programmatic API - Hands-On Findings (Task 1.12)

**Author:** Likitha Shankar
**Date:** July 10, 2026
**For:** John Trzesniak, Tanuj Pravin (LOF)
**Decides:** the Milestone 2 media approach (work plan v2, tasks 1.12 and 2.5)

## Summary

Three paths were evaluated hands-on, with actual API calls, not article reading.
The consumer NotebookLM product still has no public API. An official enterprise
API now exists but requires a paid Gemini Enterprise license and is not
accessible on our project. The decisive result: Google's Gemini text-to-speech
API generates NotebookLM-style two-speaker audio programmatically today, on the
API key the project already uses, at no additional cost on the free tier. A
25.7-second two-host patient explainer was generated in about 30 seconds as
proof. Recommendation: build per-case audio on Gemini TTS; keep manual
NotebookLM as optional supplementary content; treat video as manual-only.

## What was tested and what happened

### 1. NotebookLM consumer (notebooklm.google.com) - no API

Unchanged: no official public API. Audio and Video Overviews are manual,
through the web UI only. The manual per-diagnosis workflow documented in
`dischargeiq/media/README.md` (5 pre-generated explainers matched to the
router's diagnosis label) remains viable but does not scale to per-case audio.

Unofficial libraries exist (for example `notebooklm-py`, a reverse-engineered
client). Not acceptable for this project: it automates a consumer product
against its intended use, can break without notice, and is the wrong risk
posture for a healthcare application.

### 2. NotebookLM Enterprise API - real, but licensed and not accessible to us

Google Cloud now documents an official API:
`notebooks.audioOverviews.create` under
`https://LOCATION-discoveryengine.googleapis.com/v1alpha/...`.

Hands-on probe from our GCP project (`dischargeiq-03316`, number
1015692703359, authenticated with a live gcloud token): the `notebooks`
resource route returns 404 on both regional and global endpoints. The
route only exists for projects provisioned with **NotebookLM Enterprise under
a Gemini Enterprise license**, which we do not have.

Constraints even with a license: the API is v1alpha (Preview, pre-GA terms),
supports **audio only** (no video overview method), and allows only **one
audio overview per notebook** at a time, which would force notebook-per-case
management. Verdict: only worth revisiting if LOF already holds Gemini
Enterprise seats; not a path to buy for this feature.

### 3. Gemini TTS API - works today, on our existing key (the finding that matters)

The Gemini API exposes preview TTS models (`gemini-2.5-flash-preview-tts`,
`gemini-2.5-pro-preview-tts`, and newer) with **multi-speaker voice config**,
producing exactly the two-host podcast format NotebookLM popularized.

Hands-on proof, run July 10 with the project's existing `GOOGLE_API_KEY`
(free tier):

- Input: a short two-host dialogue script drawn from the clinician-reviewed
  heart-failure source document (`dischargeiq/media/sources/heart_failure.md`).
- Call: one `generateContent` request, `responseModalities: ["AUDIO"]`,
  two prebuilt voices (Kore, Puck).
- Output: 25.7 seconds of natural two-speaker audio (24 kHz PCM, wrapped to
  WAV), returned in about 30 seconds.
- Evidence: `evaluation/tts_demo_heart_failure.wav` (listen with
  `afplay evaluation/tts_demo_heart_failure.wav`).

Why this changes the media plan:

- **True per-case audio becomes possible.** The pipeline already produces the
  patient's structured care plan; a script-generation prompt plus one TTS call
  turns it into a personalized explainer. NotebookLM was only ever a manual
  workaround for this.
- **No new keys, accounts, or spend.** Same `GOOGLE_API_KEY`, same provider
  the whole pipeline runs on. Free-tier limits allow a handful of generations
  per day; the paid tier prices in cents per explainer if volume grows.
- **It fits the architecture we already shipped.** The media endpoint
  (`GET /media/...`), the mobile and web players, and the silent text-only
  fallback are all live and tested. TTS just becomes the generation source
  behind the same contract, which is exactly the swappable-component boundary
  the work plan promised.
- **Safety gates apply unchanged.** The script is text before it is audio, so
  the same review rules apply: grounded in the patient's document, no
  medication-change advice, plain language. Scripts can be FK-scored like any
  other agent output.

### Third-party podcast APIs (for completeness)

Commercial services (for example AutoContent API) sell NotebookLM-style
generation over REST. Rejected: adds a paid dependency and, more importantly,
sends care-plan content to an additional third-party processor, which is the
wrong direction for our privacy posture.

## Recommendation (M2 media approach)

1. **Primary: per-case audio via Gemini TTS**, generated from the patient's
   extracted care plan, served through the existing `/media` contract with the
   existing text-only fallback. Prototype next; quality pass (pronunciation,
   pacing, no advice language) per work plan task 2.5 before any tester hears it.
2. **Supplementary: the 5 manual NotebookLM per-diagnosis explainers** stay an
   option for richer produced content (sources are ready in
   `dischargeiq/media/sources/`), generated by hand when time allows.
3. **Video: manual only, Tier 3.** No API path exists on any tier we can
   access; do not build automation for it this summer.
4. **Do not pursue** NotebookLM Enterprise licensing or unofficial clients.

## Sources

- Google Cloud, NotebookLM Enterprise audio overview API:
  docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-audio-overview
- Google AI developer forum thread on programmatic Audio Overviews:
  discuss.ai.google.dev/t/notebooklm-api-use-case-programmatic-generation-of-audio-overviews
- Hands-on API calls from this repository, July 10, 2026 (model listing,
  enterprise endpoint probes, TTS generation), evidence file
  `evaluation/tts_demo_heart_failure.wav`.
