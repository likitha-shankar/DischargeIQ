# Task 1.2 — FastAPI Serverless Deployment ✅

**Deliverable:** containerized FastAPI on GCP Cloud Run.

**Commits:** Week-0 baseline (`aa8c66c` tracked the deployment assets).

**What exists:** live at https://dischargeiq-1015692703359.us-central1.run.app —
nginx multiplexes one container: `/api/*` → FastAPI, everything else →
Streamlit. Backend health: `GET /api/health`.

**Demo:** hit `/api/health`; upload through the hosted UI.
