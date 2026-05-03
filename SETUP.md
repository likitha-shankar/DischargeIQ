# DischargeIQ — Setup & Handoff Guide

> A new engineer with Python and Git experience should be able to clone and
> run DischargeIQ from scratch using only this document.

---

## What DischargeIQ Is

DischargeIQ is a web application that turns a hospital discharge PDF into
plain-language patient education content. A patient uploads their discharge
document and receives six AI-generated summaries — diagnosis explanation,
medication rationale, recovery timeline, warning signs, follow-up appointments,
and a comprehension-gap audit — displayed in a Streamlit dashboard. The system
targets post-discharge health literacy for patients who cannot understand their
discharge paperwork.

---

## Two Product Modes

DischargeIQ runs two workflows on the same pipeline:

**1. Patient chatbot**
After upload, the patient can ask plain-language questions in the chat panel.
Every answer is grounded in the uploaded discharge document; the system will
not answer from general medical knowledge.

**2. AI patient simulator (Agent 6)**
Before the patient ever sees the summary, Agent 6 reads the same discharge
document and generates questions a confused patient would ask, then scores how
many go unanswered (gap score 0–10). Care coordinators review the AI Review
tab, identify gaps, and act on them. The system surfaces gaps; humans act on
them. This is patient education and comprehension support, not clinical decision
support.

---

## System Architecture

### Six-Agent Pipeline

Runs in sequence. All six agents use the LLM provider set by `LLM_PROVIDER`
in `.env` — there is no per-agent provider split.

---

**Agent 1 — Extraction** `dischargeiq/agents/extraction_agent.py`

- **Input:** Raw PDF text extracted by pdfplumber (with `[PAGE N]` markers)
- **Output:** `ExtractionOutput` Pydantic model — diagnosis, medications (with
  dose/frequency/status/source), follow-up appointments, activity restrictions,
  dietary restrictions, red-flag symptoms, discharge condition, extraction warnings
- **Rule:** Never fabricates or infers a field. Returns `null`/`[]` when a
  field is absent in the document.

---

**Agent 2 — Diagnosis Explanation** `dischargeiq/agents/diagnosis_agent.py`

- **Input:** `primary_diagnosis`, `secondary_diagnoses`, `procedures_performed`
  from Agent 1
- **Output:** `{"text": str, "fk_grade": float, "passes": bool}`
- **Rule:** Targets FK grade ≤ 6.0. Retries once with simplification prompt if
  FK > 6.5.

---

**Agent 3 — Medication Rationale** `dischargeiq/agents/medication_agent.py`

- **Input:** `medications` list + `primary_diagnosis` + `safety_context`
  (emergency phrases harvested from raw PDF)
- **Output:** `{"text": str, "fk_grade": float, "passes": bool}`
- **Rule:** Four points per drug (why prescribed, what to notice, side effects,
  when to call). Never tells patients to stop or change a medication.

---

**Agent 4 — Recovery Trajectory** `dischargeiq/agents/recovery_agent.py`

- **Input:** `primary_diagnosis`, `procedures_performed`, `activity_restrictions`,
  `dietary_restrictions`, `red_flag_symptoms` from Agent 1
- **Output:** `{"text": str, "fk_grade": float, "passes": bool}`
- **Rule:** Week 1 / Week 2 / Weeks 3–4 / When to expect improvement. Every
  restriction from Agent 1 must appear verbatim.

---

**Agent 5 — Escalation / Warning Signs** `dischargeiq/agents/escalation_agent.py`
**Safety-critical — all output must be manually reviewed before clinical use.**

- **Input:** `primary_diagnosis`, `secondary_diagnoses`, `red_flag_symptoms`,
  `medications` from Agent 1
- **Output:** `{"text": str, "fk_grade": float, "passes": bool}`
- **Rule:** Three fixed tier headers (parsed by Streamlit UI — do not rename
  without updating the renderer):
  - `CALL 911 IMMEDIATELY`
  - `GO TO THE ER TODAY`
  - `CALL YOUR DOCTOR`
- Every red-flag symptom maps to exactly one tier. No ambiguous language.

---

**Agent 6 — AI Patient Simulator** `dischargeiq/agents/patient_simulator_agent.py`

- **Input:** Full `ExtractionOutput` from Agent 1
- **Output:** `PatientSimulatorOutput`
  - `missed_concepts` — list of questions with `answered_by_doc`, `gap_summary`,
    `severity` (critical / moderate / minor)
  - `overall_gap_score` — integer 0–10
  - `simulator_summary` — one-line summary of the biggest gap
  - `caregiver_questions` — per-item follow-up questions for meds/appointments/warnings
  - `fk_grade`, `passes` (threshold: 8.0, not 6.0)
- **Rule:** Non-fatal. If Agent 6 fails or times out, the pipeline still returns
  with `patient_simulator: null` — it does not set `pipeline_status` to `"partial"`.

---

### Orchestrator

`dischargeiq/pipeline/orchestrator.py`

Entry point: `run_pipeline(pdf_path, session_id, on_progress) → PipelineResponse`

Chains agents 1–6 in sequence, wraps each in `try/except`, reports real-time
progress via `on_progress` callbacks, and returns a `PipelineResponse` with
`pipeline_status` set to one of:

| Status                       | Meaning                                                                    |
|------------------------------|----------------------------------------------------------------------------|
| `"complete"`                 | All agents ran; no critical extraction gaps                                |
| `"complete_with_warnings"`   | All agents ran; advisory gaps detected (e.g., no follow-ups listed)        |
| `"partial"`                  | Agent 1 failed, or a critical gap exists, or any of Agents 2–5 failed      |

Wall-clock timeout: **300 seconds**. Agent 6 failure does not affect status.

---

### FastAPI Backend

`dischargeiq/main.py` — **http://127.0.0.1:8000**

> For Flutter mobile (physical device): run uvicorn with `--host 0.0.0.0`.

| Method  | Path                          | Purpose                                                          |
|---------|-------------------------------|------------------------------------------------------------------|
| `GET`   | `/health`                     | Liveness + LLM provider + DB reachability                        |
| `POST`  | `/analyze`                    | PDF upload → full pipeline → `PipelineResponse`                  |
| `GET`   | `/progress/{session_id}`      | Real-time agent progress                                         |
| `GET`   | `/pdf/{session_id}`           | Raw PDF bytes (50-entry LRU in-memory store)                     |
| `GET`   | `/simulator/{session_id}`     | Agent 6 `PatientSimulatorOutput` JSON                            |
| `POST`  | `/chat`                       | Grounded Q&A — body: `{message, session_id, pipeline_context}`   |

CORS allows all `localhost` and `127.0.0.1` origins on any port.

---

### Streamlit Frontend

`streamlit_app.py` — **http://127.0.0.1:8501**

Six-tab dashboard rendered after upload:

| Tab            | Content                                                                              |
|----------------|--------------------------------------------------------------------------------------|
| What happened  | Agent 2 — plain-language diagnosis explanation                                       |
| Medications    | Agent 3 — per-drug cards, color-coded by status (new/changed/continued/discontinued) |
| Appointments   | Agent 1 extraction — sorted by date, with source-page citation buttons               |
| Warning signs  | Agent 5 — three-tier escalation guide                                                |
| Recovery       | Agent 4 — week-by-week recovery guide                                                |
| AI Review      | Agent 6 — gap score bar, missed-concept cards by severity, caregiver questions       |

The floating chat panel calls `POST /chat` and labels answers as
"From your discharge summary" or "General guidance".

---

### Flutter Mobile App

`dischargeiq_mobile/` — **On hold. Gitignored. Not in the shared repo.**

Do not assume teammates have this directory. Revive only as a team decision.

When active: four screens (Upload → Loading → Results → Settings), same six-tab
view as Streamlit, chat panel, real-time progress via `GET /progress/{session_id}`.

> **Demo IP is hardcoded** at `lib/config.dart` line 10:
> `static const String _lanIp = '104.194.97.253';`
> Update to the actual laptop LAN IP and rebuild Flutter before any mobile demo,
> or pass `--dart-define=API_BASE=<ip>:8000` at run time.

---

### Neon PostgreSQL Database

Schema: `dischargeiq/db/schema.sql` — one table: `discharge_history`

```sql
CREATE TABLE discharge_history (
    id                SERIAL PRIMARY KEY,
    session_id        VARCHAR(64)  NOT NULL,
    document_hash     VARCHAR(64)  NOT NULL,
    primary_diagnosis VARCHAR(255),
    discharge_date    VARCHAR(50),
    pipeline_status   VARCHAR(30),          -- 'complete' | 'complete_with_warnings' | 'partial'
    extracted_fields  JSONB,
    fk_scores         JSONB,
    created_at        TIMESTAMP DEFAULT NOW()
);
```

Stores structured metadata and FK scores only. Never stores full PDF text or
raw agent outputs. The **write path** is wired in the orchestrator. The
**read path** (`get_history_for_session()` in `dischargeiq/db/history.py`)
is implemented but not yet connected to any API endpoint or UI tab.

---

## Tech Stack with Versions

From `requirements.txt`:

| Package           | Min Version | Role                                          |
|-------------------|-------------|-----------------------------------------------|
| Python            | 3.11+       | Runtime                                       |
| fastapi           | 0.110.0     | HTTP framework                                |
| uvicorn           | 0.29.0      | ASGI server                                   |
| python-multipart  | 0.0.9       | File upload parsing                           |
| streamlit         | 1.32.0      | Web UI                                        |
| anthropic         | 0.25.0      | Anthropic SDK (native)                        |
| openai            | 1.0.0       | OpenAI-compatible SDK — used for all providers|
| pdfplumber        | 0.11.0      | PDF text extraction                           |
| pypdf             | 4.0.0       | PDF utilities                                 |
| pydantic          | 2.0.0       | Data validation (v2)                          |
| asyncpg           | 0.29.0      | Async PostgreSQL driver                       |
| python-dotenv     | 1.0.0       | .env loading                                  |
| textstat          | 0.7.13      | Flesch-Kincaid readability scoring            |
| fpdf2             | 2.7.0       | PDF generation                                |
| reportlab         | 4.0         | PDF rendering                                 |
| deepdiff          | 7.0         | Deep diff (testing)                           |
| requests          | 2.31.0      | HTTP client (Streamlit → API)                 |
| pytest            | 8.x, <9.0   | Test runner                                   |

Default Anthropic model: `claude-haiku-4-5-20251001`
High-quality / eval model: `claude-sonnet-4-20250514` (set via `LLM_MODEL` in `.env`)

Flutter (if revived): Dart SDK >=3.3.0, `http ^1.2.2`, `file_picker ^8.1.4`,
`provider ^6.1.2`, `shared_preferences ^2.2.2`.

---

## Prerequisites

| Requirement          | Notes                                                                   |
|----------------------|-------------------------------------------------------------------------|
| Python 3.11+         | Verify: `python3 --version`                                             |
| Git                  | Standard install                                                        |
| Anthropic API key    | https://console.anthropic.com — free tier: 5 RPM, 10k tokens/min        |
| OpenRouter API key   | https://openrouter.ai/keys — optional, preferred for dev                |
| Neon PostgreSQL URL  | https://neon.tech — optional; only needed for history persistence       |
| Flutter SDK          | https://docs.flutter.dev/get-started/install — optional; mobile only    |

Required environment variables:

| Variable              | Required when              | Description                                               |
|-----------------------|----------------------------|-----------------------------------------------------------|
| `LLM_PROVIDER`        | Always                     | `anthropic` (default) · `openrouter` · `openai` · `ollama`|
| `LLM_MODEL`           | Optional                   | Overrides provider default (e.g., `claude-sonnet-4-20250514`) |
| `ANTHROPIC_API_KEY`   | `LLM_PROVIDER=anthropic`   | Anthropic console key                                     |
| `OPENROUTER_API_KEY`  | `LLM_PROVIDER=openrouter`  | OpenRouter key                                            |
| `OPENAI_API_KEY`      | `LLM_PROVIDER=openai`      | OpenAI platform key                                       |
| `OLLAMA_BASE_URL`     | `LLM_PROVIDER=ollama`      | Default: `http://localhost:11434/v1`                      |
| `DATABASE_URL`        | Optional                   | Neon connection string — omit to skip DB persistence      |

---

## Step-by-Step Local Setup

### 1. Clone

```bash
git clone <repo-url>
cd DischargeIQ
```

### 2. Create virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate        # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Open .env and fill in LLM_PROVIDER and the matching API key
```

Minimum `.env` for Anthropic (default):

```
LLM_PROVIDER=anthropic
LLM_MODEL=                          # Leave empty for default Haiku

ANTHROPIC_API_KEY=sk-ant-...

DATABASE_URL=                       # Leave empty to skip DB persistence
```

Missing keys raise `ValueError` at startup with a clear message.

### 5. Database setup (optional)

```bash
# Baseline schema — idempotent, safe to re-run
psql "$DATABASE_URL" -f dischargeiq/db/schema.sql

# Migration — required if DB was created before April 20, 2026
psql "$DATABASE_URL" -f dischargeiq/db/migrations/20260420_pipeline_status_width_and_check.sql
```

### 6. Run the servers

**One-command startup (macOS/Linux):**
```bash
chmod +x start.sh && ./start.sh
```
Creates `.venv` if missing, installs requirements, validates `.env`, kills stale
processes on ports 8000/8501, starts both servers. Press Ctrl-C to stop.
Flutter starts automatically if installed and `dischargeiq_mobile/` exists.

**Manual startup (two terminals):**
```bash
# Terminal 1
uvicorn dischargeiq.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2
streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

**Windows:** `start.bat`

Open **http://127.0.0.1:8501** in your browser.

---

## Switching LLM Providers

All agents share a single provider. Restart uvicorn after changing `.env`.

| Provider                | Env vars                      | Timeout | Default model                   |
|-------------------------|-------------------------------|---------|---------------------------------|
| `anthropic` (default)   | `ANTHROPIC_API_KEY`           | 60 s    | `claude-haiku-4-5-20251001`     |
| `openrouter`            | `OPENROUTER_API_KEY`          | 180 s   | `openai/gpt-4o-mini`            |
| `openai`                | `OPENAI_API_KEY`              | 60 s    | `gpt-4o-mini`                   |
| `ollama`                | `OLLAMA_BASE_URL` (optional)  | 180 s   | `llama3.2`                      |

Timeouts configured in `dischargeiq/utils/llm_client.py` line 126.

**For evaluation runs** (higher quality):
```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
```

---

## Manual Verification Script

Confirms Agents 1, 2, and 3 are working end-to-end:

```bash
python scripts/manual/agents_1_2_3_check.py
```

Run from the repo root with the virtual environment active. No `PYTHONPATH`
prefix needed — the script inserts the repo root into `sys.path` automatically.

The script runs against five hardcoded PDFs in `test-data/`:
`heart_failure_01.pdf`, `copd_01.pdf`, `diabetes_01.pdf`,
`hip_replacement_01.pdf`, `surgical_case_01.pdf`.
It does not accept command-line arguments.

**Passing output:**
```
  Documents tested   : 5
  Full chain success : 5 / 5
  Safety violations  : 0

  Acceptance gate    : PASSED
```

Gate: ≥ 3 successes and zero safety violations (no forbidden phrases like
"stop taking" or "discontinue" in Agent 3 output). Exits with code 1 on failure.

**Other manual checks:**
```bash
python scripts/manual/agent4_check.py
python scripts/manual/test_er_compatibility.py
python tests/manual/test_claude_api.py    # Verify Anthropic key
python tests/manual/test_neon_db.py       # Verify Neon DB connection
```

---

## Running the Test Suite

```bash
# Fast unit + API tests (no LLM calls, seconds)
python -m pytest dischargeiq/tests/ -v

# Skip slow tests (same as above — default behavior)
python -m pytest dischargeiq/tests/ -q

# Full corpus smoke test — real LLM, minutes to hours
python -m pytest -m slow dischargeiq/tests/test_all_corpus_smoke.py -v -s

# Hallucination gate — 8 adversarial cases
python -m pytest dischargeiq/tests/test_integration_hallucination.py -v

# Stress tests — format diversity
python scripts/stress/run_stress_fixtures.py
python scripts/stress/run_stress_fixtures.py --fixtures 9,14   # specific fixtures

# Clear pycache after editing agent files
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
```

### Adversarial fixtures (`dischargeiq/tests/fixtures/`)

**Primary 8-case hallucination gate:**

| File                                      | Scenario                                          |
|-------------------------------------------|---------------------------------------------------|
| `chf_narrative.pdf`                       | Heart failure, prose-heavy                        |
| `copd_mixed_route_change.pdf`             | COPD, IV→PO route change                          |
| `t2_diabetes_structured.pdf`              | Type 2 diabetes, structured template              |
| `hip_replacement_8pages_distractors.pdf`  | Hip replacement, 8 pages with distractors         |
| `pneumonia_abbreviations.pdf`             | Pneumonia, abbreviation-heavy                     |
| `minimal_sparse.pdf`                      | Sparse UTI discharge (partial-document stress)    |
| `aki_6_secondaries.pdf`                   | AKI with 6 secondary diagnoses                    |
| `pediatric_asthma_weight_based.pdf`       | Pediatric asthma, weight-based dosing             |

**Stress suite — format diversity:**

| File                              | Scenario                               |
|-----------------------------------|----------------------------------------|
| `fixture_09_epic_chf.pdf`         | Epic AVS-style one-pager               |
| `fixture_10_cerner_pneumonia.pdf` | Cerner narrative, dense prose          |
| `fixture_11_word_knee.pdf`        | Word-to-PDF community hospital format  |
| `fixture_12_twocolumn_mi.pdf`     | Two-column layout                      |
| `fixture_13_pediatric_appy.pdf`   | Pediatric, parent-directed letter      |
| `fixture_14_multipage_sepsis.pdf` | 6-page multi-section with distractors  |

**Additional adversarial (`adv_0X_*.pdf`):**

| File                    | Scenario                              |
|-------------------------|---------------------------------------|
| `adv_01_no_meds.pdf`    | Discharge with no medication list     |
| `adv_02_bilingual.pdf`  | Mixed English/Spanish                 |
| `adv_03_12_drugs.pdf`   | 12-drug list — stress on Agent 3      |
| `adv_04_conflicting.pdf`| Conflicting dose information          |
| `adv_05_minimal.pdf`    | Near-empty document                   |
| `adv_06_warfarin.pdf`   | Warfarin with tight INR monitoring    |

All fixture PDFs are gitignored (`dischargeiq/tests/fixtures/*.pdf`) and
exist locally only.

---

## Known Issues

> No `TODO` or `FIXME` comments exist in any `.py` file in the repository.

| Severity  | Issue                                                                                                                                                                             |
|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Minor     | **History read path not wired.** `get_history_for_session()` in `dischargeiq/db/history.py` is implemented but no API endpoint or UI tab calls it. Write path works. Missing piece: `GET /history/{session_id}`. |
| Minor     | **Flutter app gitignored.** `dischargeiq_mobile/` is local-only. Revive as a team decision, then remove from `.gitignore` and push.                                              |
| Minor     | **Flutter LAN IP hardcoded.** `lib/config.dart:10` — `_lanIp = '104.194.97.253'`. Update before any mobile demo.                                                                 |
| Minor     | **Long PDFs may timeout.** Documents >100 pages may hit the 300 s wall-clock limit. No page-count cap enforced.                                                                  |
| Minor     | **Scanned PDFs not handled.** pdfplumber requires selectable text. Image-only PDFs yield empty extraction; no OCR fallback.                                                      |
| Minor     | **Chat is stateless.** Each `POST /chat` is independent. No conversation history persisted on the backend.                                                                       |
| Warning   | **OpenRouter rate limits.** Free tier returns 429 frequently. Not reliable for demos. Use `LLM_PROVIDER=anthropic` for presentations.                                            |
| Warning   | **DB migration on existing Neon instances.** If DB was created before April 20, 2026, run `20260420_pipeline_status_width_and_check.sql` or `pipeline_status` writes will fail.  |

---

## Commit Conventions

- Prefix every commit: `DIS-<ticket>: short description`
- Only commit verified, error-free code
- Never commit `.env` or any file containing API keys
- Never commit real patient data — all test PDFs must be synthetic
- No AI authorship in commit messages, code comments, or docstrings
- The AI never runs `git commit`, `git push`, or `git add` on this repo

---

## Team

| Name                               | Role                                                             |
|------------------------------------|------------------------------------------------------------------|
| Likitha Shankar                    | Team Lead — Pipeline, Agent 1, Agent 5, Agent 6, FastAPI, Streamlit |
| Suchithra Rajkumar                 | Agent 3 (Medication), Agent 4 (Recovery)                         |
| Deepesh Kumar Appar Senthilkumar   | Agent 2 (Diagnosis)                                              |
| Manusha Boorgula                   | General contributions                                            |
| Rushi Eshwar Reddy Neelam          | General contributions                                            |
