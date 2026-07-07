# Per-diagnosis audio explainers (Sprint 4, Task 4.1)

One audio explainer per supported diagnosis, generated manually in NotebookLM
(no public API) and dropped into this directory. `GET /media/{document_type}`
serves whatever exists here; a missing file is a clean 404 and every UI falls
back to the text-only teach-back loop (fallback rule, task 6.5). Audio is an
enhancement - comprehension must never depend on it.

## Generation workflow (once per diagnosis, ~10 min each)

1. Open NotebookLM (notebooklm.google.com) with the project Google account.
2. New notebook → add sources: the clinician-reviewed template for the
   diagnosis (`dischargeiq/templates/<name>.md`) plus, optionally, one
   representative synthetic discharge PDF from `test-data/`.
3. Generate an Audio Overview. In "customize", instruct:
   "Explain this to a patient who just got home from the hospital.
   Plain language, short sentences, 6th-grade level. No medical jargon.
   Do not give medication-change advice."
4. LISTEN TO THE WHOLE FILE before shipping it (media quality pass,
   Task 4.2): pronunciation of drug names, no invented guidance, no
   'consider stopping' language. Hard rule 2 applies to audio too.
5. Download and save here with the exact router label as the filename:

   | File | Diagnosis |
   |---|---|
   | `heart_failure.m4a` | Heart failure |
   | `copd.m4a` | COPD |
   | `diabetes.m4a` | Diabetes management |
   | `hip_replacement.m4a` | Hip replacement |
   | `surgical.m4a` | Surgical / laparoscopic |

   (`.mp3` / `.wav` also work; `.m4a` is preferred - NotebookLM's export.)

6. Restart the backend (or redeploy) - no code change needed.

## Rules

- English first; Spanish variants (task 4.3, stretch) would be
  `<label>_es.m4a` - NOT wired yet, cut first if velocity slips.
- Files here are content, not code: no patient data, ever.
- Do not regenerate mid-clinical-review - reviewers score against the
  media quality pass (Task 4.2) snapshot.
