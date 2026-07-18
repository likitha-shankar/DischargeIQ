# Task 2.4 - NotebookLM Hands-On API Evaluation ✅

**Deliverable:** actual programmatic calls (not article reading) establishing
whether audio/video overviews can be generated per case, the constraints, and
the fallback. This report decides the Sprint 3 media approach.

**For:** John and Tanuj (Leap of Faith, LLC)
**Date:** July 18, 2026
**Evaluated by:** Likitha Shankar, against GCP project `dischargeiq-502723`

## Findings from live calls

**1. An official NotebookLM API now exists - but it is enterprise-licensed.**
Google documents a `v1alpha` API under Gemini Enterprise (product renamed
"Gemini Notebook" in July 2026): notebook CRUD, source management, and
`notebooks.audioOverviews.create` for programmatic Audio Overviews, on
`*-discoveryengine.googleapis.com`.

**2. Hands-on call result (July 18).** With the Discovery Engine API enabled
on our project, `POST /v1alpha/projects/678599658918/locations/us/notebooks`
returns:

```
400 FAILED_PRECONDITION
"User must be assigned a license in order to be granted access, the license
 must have a subscription tier that is not unspecified. Required license for
 this request is SUBSCRIPTION_TIER_NOTEBOOK_LM."
```

The gate is a per-seat Gemini Enterprise / NotebookLM Enterprise
subscription assigned to the calling user - an organizational procurement,
not something GCP trial credits or a standard API key can satisfy. The
consumer NotebookLM (notebooklm.google.com) still has no public API;
community wrappers automate the web UI and are unsuitable for a healthcare
product (ToS and stability risk).

**3. Documented constraints of the enterprise API** (relevant if LOF ever
licenses it): one audio overview per notebook at a time; generation takes
minutes; per-case use would mean notebook-create + source-upload +
overview-create + poll per patient session.

**4. The fallback path already works, verified live today.** Our per-case
pipeline (patient's structured care plan → two-host dialogue script via the
chat LLM → Gemini multi-speaker TTS) generated a valid 81-second two-voice
WAV in ~40s total (script 2.6s, synthesis 37.2s). The TTS model
(`gemini-2.5-flash-preview-tts`) draws on a separate quota bucket from the
pipeline agents - it worked even while the chat bucket was exhausted.

## Recommendation (decides Sprint 3, task 3.2)

**Ship per-case audio on the Gemini TTS path we own.** It is programmatic
today, per-patient (built from THEIR document, not a generic explainer),
inside our existing safety rails (grounded-only script prompt, FK check,
Task 4.2 human listen-through before anything ships), and costs no new
licensing. The work-plan's component boundary held: NotebookLM was swapped
for another text-to-audio technology without touching the pipeline.

NotebookLM proper remains a manual option for pre-generated per-diagnosis
assets via the web UI, and the enterprise API is worth revisiting only if
LOF acquires Gemini Enterprise seats for other reasons.

## Sources

- Audio overview API: docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-audio-overview
- Notebook API: docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks
- RPC reference: docs.cloud.google.com/gemini/enterprise/docs/reference/rpc/google.cloud.notebooklm.v1alpha
