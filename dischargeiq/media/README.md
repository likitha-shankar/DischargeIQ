# Per-diagnosis audio + video explainers (Sprint 4, Task 4.1)

One audio explainer (podcast) and optionally one video explainer per
supported diagnosis, generated manually in NotebookLM (no public API) and
dropped into this directory. `GET /media/{document_type}` serves the audio,
`GET /media/{document_type}/video` the video; a missing file is a clean 404
and every UI falls back to the text-only teach-back loop (fallback rule,
task 6.5). Media is an enhancement - comprehension must never depend on it.

## Generation workflow (once per diagnosis, ~10 min audio / ~15 min video)

1. Open NotebookLM (notebooklm.google.com) with the project Google account.
2. New notebook → add ONE source: the ready-made NotebookLM source doc for the
   diagnosis in `dischargeiq/media/sources/<router_label>.md`. These are the
   clinician-reviewed template text (verbatim, no added facts) pre-formatted
   with bulleting and phonetic hints - the Task 4.2 pacing/pronunciation lever.
   (Optionally also add one representative synthetic PDF from `test-data/`.)
3. Generate an **Audio Overview** (podcast) and, if wanted, a **Video
   Overview**. In "customize", instruct:
   "Explain this to a patient who just got home from the hospital.
   Plain language, short sentences, 6th-grade level. No medical jargon.
   Do not give medication-change advice."
4. LISTEN TO / WATCH THE WHOLE FILE before shipping it (media quality pass,
   Task 4.2): pronunciation of drug names, no invented guidance, no
   'consider stopping' language. Hard rule 2 applies to audio and video too.
5. Download and save here with the exact router label as the filename:

   | Audio (podcast) | Video | Diagnosis |
   |---|---|---|
   | `heart_failure.m4a` | `heart_failure.mp4` | Heart failure |
   | `copd.m4a` | `copd.mp4` | COPD |
   | `diabetes.m4a` | `diabetes.mp4` | Diabetes management |
   | `hip_replacement.m4a` | `hip_replacement.mp4` | Hip replacement |
   | `surgical.m4a` | `surgical.mp4` | Surgical / laparoscopic |

   (Audio also accepts `.mp3`/`.wav`; video also accepts `.webm`. `.m4a` +
   `.mp4` are NotebookLM's exports. Audio and video are independent - ship
   either, both, or neither per diagnosis.)

6. Restart the backend (or redeploy) - no code change needed.

## Rules

- English first; Spanish variants (task 4.3, stretch) would be
  `<label>_es.m4a` - NOT wired yet, cut first if velocity slips.
- Files here are content, not code: no patient data, ever.
- Do not regenerate mid-clinical-review - reviewers score against the
  media quality pass (Task 4.2) snapshot.
