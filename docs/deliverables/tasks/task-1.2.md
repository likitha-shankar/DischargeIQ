# Task 1.2 - FastAPI Serverless Deployment ✅

**Deliverable:** containerized FastAPI on GCP Cloud Run.

**Commits:** Week-0 baseline (`aa8c66c` tracked the deployment assets).

**What exists:** live at https://dischargeiq-1015692703359.us-central1.run.app -
nginx multiplexes one container: `/api/*` → FastAPI, everything else →
Streamlit. Backend health: `GET /api/health`.

**Demo:** hit `/api/health`; upload through the hosted UI.

## Redeploy - Gemini migration + current code (Jul 7, 2026)

Project `dischargeiq-03316`, service `dischargeiq`, region `us-central1`.
Redeployed to revision `dischargeiq-00003-pmg` (100% traffic) with the current
backend code and the Gemini provider switch. `GOOGLE_API_KEY` was added (the
service was anthropic-only before, so an env flip alone would not work - a
full source redeploy was required).

```bash
gcloud run deploy dischargeiq --source . --region us-central1 \
  --allow-unauthenticated \
  --update-env-vars LLM_PROVIDER=gemini,LLM_MODEL=gemini-2.5-flash-lite,\
LLM_FALLBACK_PROVIDER=anthropic,GOOGLE_API_KEY=<from .env, never echoed>
```

- `.gcloudignore` (commit `c503423`) keeps the 1.8GB Flutter app, frontend
  `node_modules`, `_archive`, and `dist` out of the Cloud Build upload.
- Verified live: `/api/health` → `llm_provider: gemini`; `/api/media/{type}`
  and `/api/media/{type}/video` respond (new code); a live `/analyze` had the
  router classify on Gemini successfully (key works end to end).
- Known: Gemini free-tier daily quota can 429 mid-pipeline until it resets;
  the `anthropic` fallback covers provider failures but not a shared-quota day.
