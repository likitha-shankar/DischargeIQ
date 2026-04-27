<!--
File: LEARNERS.md
Owner: Likitha Shankar
Description: Short learner-facing entry to the repo — status table, core concepts
  (pipeline, PipelineResponse, FK, partial runs, single LLM provider), minimal run
  commands, and pointers to README vs CLAUDE for depth.
Maintained for: Classmates and new contributors before they read CLAUDE.md.
-->

# DischargeIQ — Learner guide & project status

This file is the **friendly entry point** for anyone learning the codebase or reporting status in class. For deep technical detail aimed at AI tooling, see [`CLAUDE.md`](CLAUDE.md). For install and commands, see [`README.md`](README.md).

---

## Project status (snapshot)

| Area | What it is | Status |
|------|------------|--------|
| **Backend** | FastAPI app, `/analyze` PDF upload, multi-agent pipeline | Core path implemented; depends on `.env` keys and provider quotas |
| **Agents 1–5** | Extract → 4 education sections + FK checks | Implemented under `dischargeiq/agents/` and `dischargeiq/pipeline/` |
| **Web UI** | Streamlit dashboard | Run via `./start.sh` → http://127.0.0.1:8501 |
| **API** | Uvicorn | Default http://127.0.0.1:8000 |
| **Tests** | Integration / smoke tests | See `README.md` and `dischargeiq/tests/` |
| **iOS app** | SwiftUI client (was planned for `ios/`) | **On hold**; `ios/` is in `.gitignore` (local-only until revived) |

**Blockers you might hit:** missing or invalid API keys, provider **429** rate limits (e.g. free tier), or local LLM not running if using Ollama.

---

## What you are learning (concepts)

1. **Pipeline** — A PDF goes in; **Agent 1** extracts structured facts; **Agents 2–5** turn those into plain-language sections at a controlled reading level.
2. **`PipelineResponse`** — The JSON shape the API returns (diagnosis text, medication rationale, recovery, escalation, extraction details, warnings, status).
3. **FK (Flesch–Kincaid)** — Readability scoring used as a guardrail; scores appear in responses as `fk_scores`.
4. **Partial runs** — If one step fails (e.g. rate limit), the pipeline may still return a **partial** result with warnings; the UI surfaces that.
5. **One LLM provider for all agents** — `LLM_PROVIDER` in `.env` applies to every agent (not “Agent 1 only”). For Claude, pin `LLM_MODEL=claude-sonnet-4-20250514`.

---

## How to run (minimal)

From the repo root:

```bash
./start.sh
```

Fill `.env` when prompted (see `.env.example`). Backend: **8000**, Streamlit: **8501**.

---

## Where important things live

| Path | Purpose |
|------|---------|
| `dischargeiq/main.py` | FastAPI entry |
| `dischargeiq/pipeline/` | Orchestration |
| `dischargeiq/models/` | Pydantic API models |
| `streamlit_app.py` | Web dashboard |
| `ios/` (if present locally) | SwiftUI client — **not in Git** (`.gitignore`); on hold |

---

## iOS app (on hold)

The mobile client is **paused** for the team repo: the **`ios/`** folder is gitignored so work stays on each machine. If you still have a local copy, it would call **`POST /analyze`** like any other client; **Streamlit + FastAPI** are the supported demo path for now.

---

## Suggested order for new contributors

1. Read this file and [`README.md`](README.md).
2. Run `./start.sh` and upload a PDF in Streamlit.
3. Skim `dischargeiq/pipeline/` to see how agents are chained.
4. Read **`CLAUDE.md`** → section *Current project status (detailed)* for AI-oriented context.

---

## Course / team context

Graduate project (CS 595, IIT Chicago, Spring 2026), LOF Patient Engagement pillar. Team roles and ticket owners are summarized in [`CLAUDE.md`](CLAUDE.md).

---

*Last updated: aligns with repo layout as of Spring 2026; adjust the status table when milestones change.*
