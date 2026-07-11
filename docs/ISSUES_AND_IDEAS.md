# DischargeIQ - Issues and Ideas Log

Internal tracking document (Work Plan v2, task 2.7), kept per John's guidance:
blockers and open questions to clear, plus ideas parked for later so nothing
is lost. For the developer's own clarity; available at reviews on request.
Newest entries first within each section.

## Open issues / blockers

| # | Issue | Status / next step |
|---|---|---|
| I-10 | Gemini free tier is 20 requests/day/model; one full pipeline run is ~8 calls, so ~2 runs/day before degradation. Fallbacks currently unfunded (Anthropic $0) or congested (OpenRouter :free upstream). | Demo-day risk #1. Fund one fallback (~$5-10) or move primary to paid tier before tester runs. Meanwhile: rehearse early on fresh quota; flip LLM_MODEL to gemini-2.5-flash for a second free bucket. |
| I-9 | Router degrades to document_type=unknown when its LLM call fails, so media matching would miss (text fallback covers it). Seen live July 11 under a Gemini 503. | Acceptable by design (never drop a real discharge). Revisit only if it shows up with funded quota. |
| I-8 | In-memory PDF/session stores are process-local; a Cloud Run scale-out or restart 404s /pdf/{session}. | Known limitation, documented. GCS/Redis shared store is the fix, deferred (not needed for beta scale, max-instances=1). |
| I-7 | iOS on-device delivery blocked on Apple access. | Research-before-spend order agreed: LOF shared account (ask Steve), free 7-day provisioning for demos, $99 only if LOF confirms. |
| I-6 | Two human-dependent items: 10 testers (Tanuj coordinating), repo arrangement with John (Bitbucket copy + license). | Chase in the next check-in. |
| I-5 | Adversarial audit (Task 5.3) last ran vacuously - both providers exhausted, so injections never touched a live model. | Re-run on funded quota / fresh free quota for a valid result before quoting it as evidence. |
| I-4 | streamlit_app.py is ~6,000 lines (12x the repo's 500-line rule). New tabs already go in ui/. | Split during Sprint 6 polish, not before the demo. |
| I-3 | Calendar star (task 2.2) needs an add-to-calendar action, which does not exist yet. | Build a calendar deep-link on the Appointments tab first, then the star. M2 candidate. |
| I-2 | Backup demo recording (LOF guide section 9) not yet cut. | Record the first clean fresh-quota run - kills two birds. |
| I-1 | Media quality pass (Task 4.2) pending: no generated audio has had a human listen-through. | Gate before ANY audio reaches a tester; applies to TTS output and manual NotebookLM files alike. |

## Decisions on record

| # | Decision | Why |
|---|---|---|
| D-4 | Do NOT use notebooklm-py (or any reverse-engineered NotebookLM client) in the product. | Automates a consumer service against its ToS with personal account cookies; can break or cost the Google account any day; opposite of the comply-and-point compliance posture; the official Gemini TTS path already delivers per-case audio on our key. (Evaluated July 11 after it surfaced in research and again via community recommendation.) |
| D-3 | Per-case audio via Gemini TTS, not NotebookLM Enterprise. | Enterprise API needs a paid Gemini Enterprise license, is v1alpha audio-only, and 404s on our project. TTS is official, free-tier, proven hands-on (Task 1.12 findings). |
| D-2 | Clinician involvement = sampled verification with a checklist, not 50-document scoring. | July meeting: reviewers verify, they do not test; 50-doc scoring was rejected as unrealistic. |
| D-1 | 3D anatomy explainer removed from the tree. | Out of scope per the accepted work plan; kept privately as future material (trade-secret guidance). |

## Ideas parked for later (NOT current scope)

| # | Idea |
|---|---|
| P-5 | Add-to-calendar deep link on Appointments tab (also unlocks the calendar star). |
| P-4 | Per-case VIDEO explainers if/when an official API path exists (no tier we can access has one today). |
| P-3 | Spanish support - explicit stretch, first cut (work plan 4.3). |
| P-2 | GCS/Redis shared session store for multi-instance PHI-grade serving. |
| P-1 | Caregiver share view - export the plain-language summary for a family member. |
