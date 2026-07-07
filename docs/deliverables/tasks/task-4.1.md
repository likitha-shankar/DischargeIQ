# Task 4.1 - Media Workflow + In-App Audio (scaffolding built early) ◑

**Deliverable:** care plan → NotebookLM audio → app. Decision (Jul 7):
**per-diagnosis** audio - NotebookLM has no public API, so the team generates
ONE explainer per supported diagnosis manually; the app matches the router's
`document_type` and plays the right one. Personalized per-session audio was
rejected as infeasible at beta scale.

**Commit / tag:** pending review - suggested tag `task-4.1-media-scaffold`

**What is built (code path, no LLM cost):**
- `PipelineResponse.document_type` - the router classification now rides the
  API response (also useful for analytics).
- `GET /media/{document_type}` (`dischargeiq/api/routes/media.py`) - serves
  `dischargeiq/media/<label>.{m4a,mp3,wav}`. Boundary-validated against the
  closed router-label set (path traversal dead). **404 is the normal "not
  generated yet" answer** - fallback rule 6.5: every UI degrades silently to
  the text-only teach-back loop; media never blocks comprehension.
- Streamlit: "Prefer to listen?" player at the top of the What Happened tab,
  shown only when the audio exists (5-min cache; network errors degrade the
  same as 404). Caption clarifies the audio is general for the condition,
  the written summary is specific to the patient's document.
- Mobile player: deferred - needs an audio dependency (`just_audio` or
  `audioplayers`) decision; Streamlit demonstrates the flow for the
  Tranche 3 gate.

**What stays manual (the workflow, documented in
`dischargeiq/media/README.md`):** generate 5 Audio Overviews in NotebookLM
from the clinician-reviewed templates, LISTEN TO EACH before shipping
(Task 4.2 quality pass - drug pronunciation, no medication-change advice),
save as `<router_label>.m4a` in `dischargeiq/media/`, restart backend.
No code change to add or replace audio.

**Verified:** 3 endpoint tests green (allowlist, clean 404, happy-path serve
with correct MIME); full backend suite 88 passed.

**Remaining for ✅:** generate the 5 real audio files (Likitha, ~1 hour) and
run the Task 4.2 quality pass on them.
