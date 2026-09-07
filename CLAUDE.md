<!--
File: CLAUDE.md
Owner: Likitha Shankar
Description: Long-form project handbook for AI assistants - architecture, locked Agent 1
  schema, pipeline contracts, API overview, team DIS ownership, testing map, and strict
  rules (e.g. no agent-authored commits, no real PHI). Complements README operational steps.
Maintained for: Course team and Cursor/Claude context; keep "Current project status" accurate.
-->

# DischargeIQ - Project Context for AI Agents

## LOF LABS program rules (binding - read every run)

Full rules: **[docs/LOF_LABS_RULES.md](docs/LOF_LABS_RULES.md)** (authoritative;
wins over any older text here). Compact version:

- **Solo project.** Likitha Shankar is the sole developer. Never add other
  names to code, docs, commits, licenses, or headers.
- **13 weeks, 4 phases, 3 gates** (NOT "tranches" - ignore that older word).
  Gate 1 concept (Wk2, $500), Gate 2 working prototype (Wk6, $1,250), Gate 3
  feature-complete beta (Wk10, $1,250), Final demo (Wk13, $2,000). One-week
  cure window per gate. Judged against a fixed bar, not other teams.
- **Every gate checks:** LICENSE at root (Apache-2.0, done), current
  `DEPENDENCIES.md` manifest (done), no GPL/AGPL/network-copyleft deps, and no
  clinical OR synthetic/eval data in a PUBLIC repo without written approval.
- **Repo:** authoritative repo must be the LOF-controlled org (pending access).
  Until then it lives at `github.com/likitha-shankar/DischargeIQ`, **PRIVATE
  since 6 Sep 2026**. Confirm privacy before every push: the program rule
  above allows clinical/eval data only in a PRIVATE repo.
  **Do not verify this by checking `test-data/mtsamples/`.** The corpus itself
  has never been committed (it is gitignored and rebuilt from scripts), so
  that directory looks clean whatever the real state is. This file claimed the
  opposite until 6 Sep 2026 and the wrong check passed for weeks while
  `evaluation/corpus_outputs_prefix_backup/` - 61 pipeline outputs carrying
  verbatim source quotes in their `_source` fields - sat in a public repo.
  The reliable check is for DERIVED clinical text, which is what actually gets
  committed by accident:

  ```bash
  gh repo view --json visibility          # must be PRIVATE
  git ls-files | grep -E 'corpus_outputs|mtsamples|test-data/fax'   # expect none
  ```
- No unsupported clinical claims; assist/summarize/educate/triage only (already
  the HITL framing + hard rules below).

## What this project is

DischargeIQ is two things working together:

1. **A patient-friendly chatbot** grounded in the uploaded discharge document.
   Patients ask plain-language questions; the chat panel answers from the doc.
2. **An AI simulation layer** that reads the same discharge document and
   surfaces "missed concepts" - questions a confused patient would ask that
   the document does not answer - before the patient ever sees the summary.

A patient uploads a PDF of their discharge document and receives output from
six specialised agents. Both UIs show **seven** tabs: the six agent outputs
below plus "Test yourself", the teach-back quiz (see the July 2026 status
section for the full tab order).

1. What Happened to You (Agent 2 - diagnosis explanation)
2. Your Medications Explained (Agent 3 - per-drug rationale)
3. Your Recovery Timeline (Agent 4 - week-by-week guide)
4. Warning Signs: When to Get Help (Agent 5 - three-tier escalation decision tree)
5. Your Follow-Up Appointments (Agent 1 extraction - sorted, with source citations)
6. AI Review (Agent 6 - AI patient simulator: gap score 0–10, missed concepts)

The AI surfaces gaps; a human (care coordinator, nurse, or the patient's own
care team) acts on them. The system never takes clinical responsibility.

This is a graduate course project (CS 595, IIT Chicago, Spring 2026).
It targets the LOF Patient Engagement pillar. The primary use case is
post-discharge health literacy for patients who do not understand their
discharge documents.

## Current project status (detailed) - for AI assistants

**Last reviewed:** July 2026 (LOF summer engagement, Week 2). Treat this section
as the source of truth for “what is happening now.” Older sections below (e.g.
dated milestones) may be stale.

**Summer engagement (July 2026):** DischargeIQ is a funded LOF LABS project
(13 weeks, 4 phases, 3 gates - see the program-rules section at the top of
this file and `docs/LOF_LABS_RULES.md`). Work plan:
`docs/deliverables/README.md` maps every deliverable to commits and demo tags. New since June: supervisor/router agent, cross-provider
LLM failover, Vertex AI (BAA) provider path, the de-identified test corpus
(`test-data/mtsamples/`, 106 documents - it replaced the generated 50-document
synthetic corpus on 30 Jul 2026 and generated documents are no longer used for
evaluation), and the teach-back quiz loop
(`/quiz/generate`, `/quiz/score`, `quiz_scores` table, quiz UIs on mobile and
Streamlit). Comprehension-lift target: 13% baseline → 50–70%.

### Where the product stands

- **End-to-end pipeline is implemented:** PDF upload → Agent 1 extraction →
  Agents 2–5 (diagnosis, medication, recovery, escalation) → Agent 6 (AI patient
  simulator, non-fatal) → FK checks → `PipelineResponse` JSON. Orchestration lives
  in `dischargeiq/pipeline/orchestrator.py`.
- **Primary surface for demos:** **Streamlit** (`streamlit_app.py`), started by
  `./start.sh` (or `start.bat` on Windows). Default URL: http://127.0.0.1:8501.
- **Backend:** FastAPI in `dischargeiq/main.py`, typically http://127.0.0.1:8000.
- **Hosted deployment (verified 25 Aug 2026):** Cloud Run, project
  `dischargeiq-502723`, revision `dischargeiq-00022-mdb`. nginx multiplexes
  one container: `/api/*` → FastAPI, everything else → Streamlit. Backend
  health check is `GET /api/health` (plain `/health` returns Streamlit HTML).
  Two URLs serve the same service, both verified 200:
  - `https://dischargeiq-678599658918.us-central1.run.app` - **the one the
    mobile app calls**, hardcoded in `dischargeiq_mobile/lib/config.dart`
  - `https://dischargeiq-dyzqwhs5va-uc.a.run.app` - what
    `gcloud run services describe` reports

  **Do not use `https://dischargeiq-1015692703359.us-central1.run.app`.** It
  is the pre-July-2026 project and now returns **503**. This file advertised
  it until 25 Aug 2026, which cost a demo-eve panic about a backend that was
  perfectly healthy. Verify against `config.dart`, not against docs.
- **Failure mode:** The pipeline is designed to return **`pipeline_status` of
  `"complete"`, `"complete_with_warnings"`, `"partial"`, or `"rejected"`** (not to crash
  on bad PDFs or LLM failures). `"partial"` runs may occur when an agent fails, rate
  limits hit (429), timeouts occur, or keys are missing. `"complete_with_warnings"` means
  all agents ran but extraction completeness warnings were raised - including
  critical ones. **A missing section is never `"partial"`.** August 2026: the
  orchestrator used to downgrade to `"partial"` when medications or red flags
  were absent, which on the real corpus (medications in 62% of documents,
  warning signs in 34%) told most patients "our reading service was busy"
  about a section the hospital never wrote. `"partial"` now means THIS SYSTEM
  failed and retrying may help; gaps in the source are
  `"complete_with_warnings"`. Non-discharge uploads are the router's job. `"rejected"` (July 2026)
  means the router gated a non-discharge document (bill, EOB, invoice) BEFORE any agent
  ran; `rejection_reason` carries the router's one-sentence explanation and both UIs show
  a dedicated "try another document" screen instead of results tabs.

### LLM and environment configuration

- **Single provider for all agents:** Every agent reads **`LLM_PROVIDER`**
  (default **`gemini`** as of June 2026) via shared helpers in `dischargeiq/utils/llm_client.py`.
  Also supported (July 2026): **`vertex`** - same Gemini models through a GCP
  project under BAA (requires `VERTEX_PROJECT`, ADC auth; the REQUIRED path for
  real patient data), and **`LLM_FALLBACK_PROVIDER`** (default anthropic) for
  one automatic cross-provider failover attempt.
  Agents 1, 2, 6 use `get_llm_client()` (OpenAI-compat client for all providers).
  Agents 3–5 use `get_native_agent_client(provider)` - returns native `anthropic.Anthropic`
  on the `anthropic` path and the OpenAI-compat client for all other providers (gemini,
  openrouter, openai, ollama). There is **no** split where only one agent uses a different
  backend - switching `LLM_PROVIDER` in `.env` switches **every** agent.
- **Default provider: Gemini.** Default model: `gemini-2.5-flash-lite`. Override with
  `LLM_MODEL=gemini-2.5-flash` for higher quality. For Anthropic: set
  `LLM_PROVIDER=anthropic` and `LLM_MODEL=claude-haiku-4-5-20251001` (cheapest) or
  `claude-sonnet-4-20250514` for eval. **Always use dated Anthropic model IDs** - undated
  aliases can **404**.
- **Primary key: `GOOGLE_API_KEY`** (required when `LLM_PROVIDER=gemini`). Also available:
  `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, optional `OLLAMA_BASE_URL`.
  Missing keys raise **`ValueError`** with a clear message from `require_provider_api_key()`
  rather than a raw **`KeyError`**.
- **`DATABASE_URL`** supports Neon PostgreSQL (history / persistence) where wired;
  local development may work without DB for core `/analyze` paths-confirm in code
  paths if debugging save failures. DB pool is now long-lived (created at startup via
  FastAPI lifespan, closed at shutdown) - no longer created per request.

### HTTP API (FastAPI)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| POST | `/analyze` | Multipart PDF upload; runs full pipeline |
| GET | `/pdf/{session_id}` | Retrieve stored PDF bytes for session (used with Streamlit viewer) |
| POST | `/chat` | Grounded chat answer. Body: `message`, `session_id`, `pipeline_context` (CORS enabled for Streamlit origins) |
| POST | `/quiz/generate` | Teach-back quiz: **up to 5** non-leading MCQs from the session's extraction (the prompt asks for exactly 5; questions that fail validation are dropped and the agent raises below 3, so a sparse document legitimately yields 4). Body: `session_id`, `extraction`. Stateless; rate-limited 10/min |
| POST | `/quiz/score` | Score one quiz phase. Body: `session_id`, `phase` (`pre`\|`post`), `question_keys`, `answers`. Persists to `quiz_scores` (non-fatal without DB); post phases return `comprehension_delta` vs the first stored pre score |

### Frontend and tooling

- **Streamlit** is the main MVP UI; it talks to the API (including `/chat` with CORS).
- **Streamlit UI has 7 tabs (July 2026):** What Happened / Medications / Appointments /
  Warning Signs / Recovery / **Test yourself** / AI Review. The AI Review tab surfaces
  Agent 6 output (gap score bar, missed-concept cards by severity, answered-concept
  expander). The tab is always visible - Agent 6 runs on every upload (non-fatal
  fallback on failure). "Test yourself" is the teach-back quiz loop (`ui/quiz_tab.py`);
  new Streamlit tabs go in the `ui/` package, never into streamlit_app.py.
- **PRODUCT PRIORITY (July 2026):** the Flutter mobile app (`dischargeiq_mobile/`)
  is the MAIN product; Streamlit is the fallback/demo surface. Mobile development
  is UNFROZEN. The app has upload → results (7 tabs incl. "Test yourself" quiz) →
  chat, and talks to the same API.
- **HITL framing:** The AI Review tab opens with a patient-facing notice that
  gaps are for discussion with their care team, not medical diagnoses.
- **iOS / SwiftUI client:** Development is **on hold** for the shared repo.
  The entire **`ios/`** directory is listed in **`.gitignore`** so it stays
  **local-only** until it is turned back on. It is not in the repo, so a
  fresh clone will not have it.
- **Flutter app (`dischargeiq_mobile/`):** On hold, but the source IS tracked
  in Git (~92 files). Only build artifacts (`build/`, `.dart_tool/`,
  `pubspec.lock`, plugin files) are gitignored. Verified June 2026.

### Testing

Notable tests under `dischargeiq/tests/`:

- `test_integration_hallucination.py` - integration / hallucination gates (see README).
- `test_api_guardrails.py` - API behavior and guardrails.
- `test_resilience_hardening.py` - retries, OpenRouter error paths.
- `test_all_corpus_smoke.py` - corpus smoke coverage.

Additional scripts and stress runners are documented in **`README.md`**.

### Documentation map

| File | Audience |
|------|----------|
| `README.md` | Install, run, test commands |
| `LEARNERS.md` | Short learner-oriented status and file map |
| `CLAUDE.md` (this file) | Agents: architecture, rules, contracts |

### Known operational pain points

- **OpenRouter free tier / rate limits:** Frequent **429** responses; pipeline may
  go **partial** or retry per `llm_client.py`.
- **Multi-key setup:** Default provider is now **Gemini** - new contributors need
  `GOOGLE_API_KEY`. If using Anthropic instead, set `LLM_PROVIDER=anthropic` and
  `ANTHROPIC_API_KEY`. OpenRouter/OpenAI paths also available.
- **In-memory PDF store is process-local:** `_pdf` and `_simulator` in
  `dischargeiq/services/session.py` (owned by `session_store`) are per-process
  `OrderedDict`s. `main.py` only re-exports them as `_pdf_store` /
  `_simulator_store` for older tests - do not debug there. Under Cloud Run with `max-instances > 1`,
  a `GET /pdf/{session_id}` may land on a different instance than the `POST /analyze`
  that stored it, returning 404. Long-term fix requires GCS or Redis - not yet wired.
- **Mobile apps frozen:** `ios/` (SwiftUI) is gitignored and local-only.
  `dischargeiq_mobile/` (Flutter) source is tracked in Git but development is
  frozen; only its build artifacts are gitignored.
- ~~No automatic LLM cross-failover~~ **RESOLVED July 2026:** `call_chat_with_fallback`
  now makes one failover attempt on `LLM_FALLBACK_PROVIDER` (default anthropic,
  `none` disables) when the primary provider fails after its retries. Covers all
  agents on the OpenAI-compat path. If both providers fail, behavior is the old
  one: **partial** with section-level warnings.

## Team

Solo project - Likitha Shankar (sole developer: backend, frontend, LLM, data).

## Tech stack

- Backend: FastAPI + Python 3.11+
- LLM: Configurable - all agents share `LLM_PROVIDER` (default: **gemini**).
  Agents 1/2/6 use OpenAI-compat client via `get_llm_client()`. Agents 3–5 use
  `get_native_agent_client()` - native Anthropic SDK on `anthropic` path, OpenAI-compat
  on all others. Default Gemini model: `gemini-2.5-flash-lite` (see `llm_client.py`).
- Database: Neon PostgreSQL (asyncpg)
- Frontend: Streamlit (MVP) or React
- PDF parsing: pdfplumber
- Readability scoring: textstat (Flesch-Kincaid)
- Environment: python-dotenv, Pydantic v2

## Repo structure
```
dischargeiq/
├── main.py                    # FastAPI entry point
├── requirements.txt
├── .env.example               # GOOGLE_API_KEY= (primary), ANTHROPIC_API_KEY=, DATABASE_URL=
├── .gitignore                 # must include .env
├── agents/
│   ├── extraction_agent.py         # Agent 1 - structured extraction
│   ├── diagnosis_agent.py          # Agent 2 - diagnosis explanation
│   ├── medication_agent.py         # Agent 3 - medication rationale
│   ├── recovery_agent.py           # Agent 4 - recovery timeline
│   ├── escalation_agent.py         # Agent 5 - escalation / warning signs
│   └── patient_simulator_agent.py  # Agent 6 - AI patient simulator (gap scoring)
├── models/
│   ├── extraction.py          # Pydantic ExtractionOutput model
│   └── pipeline.py            # Pydantic PipelineResponse + PatientSimulatorOutput
├── pipeline/
│   └── orchestrator.py        # Async orchestrator - wires all 6 agents;
│                              #   Agents 2–5 run in parallel via asyncio.gather
├── prompts/
│   ├── agent1_system_prompt.txt
│   ├── agent2_system_prompt.txt
│   ├── agent3_system_prompt.txt
│   ├── agent4_system_prompt.txt
│   ├── agent5_system_prompt.txt
│   ├── agent6_system_prompt.txt
│   └── llm_judge_prompt.txt
├── utils/
│   ├── scorer.py              # fk_score(), fk_check(), log_fk_score() (thread-safe CSV write)
│   ├── llm_client.py          # get_llm_client(), get_native_agent_client(), load_agent_prompt(),
│   │                          #   call_chat_with_fallback()
│   ├── extraction_scope.py    # Field scoping per agent
│   ├── logger.py              # Shared logger config
│   └── warnings.py            # assess_extraction_completeness()
├── db/
│   └── history.py             # save_discharge_history(), get_history_for_session()
│                              # NOTE: dischargeiq/templates/ is EMPTY (.gitkeep
│                              #   only). The templates live at the REPO ROOT,
│                              #   outside this package - see below.
├── test-data/                 # de-identified corpus (mtsamples/, 106 docs)
│                              #   + 3 demo/beta sample PDFs at the top level
├── evaluation/
│   ├── fk_log.csv
│   ├── agent1_baseline.md
│   ├── api_cost_estimate.md
│   ├── test_cases.json
│   ├── judge_results.json
│   ├── fk_delta_table.csv
│   └── evaluation_summary.md
└── docs/
    ├── extraction_schema.json
    └── extraction_schema_notes.md
```

## Templates live at the repo root, not inside the package

Corrected 25 Aug 2026. This file previously showed five diagnosis templates
under `dischargeiq/templates/`. That directory contains only `.gitkeep`. The
real locations are:

```
templates/                     # REPO ROOT - diagnosis explanation templates
├── heart_failure.md           #   reference/eval material for Agent 2.
├── copd.md                    #   NOT loaded automatically by the pipeline.
├── diabetes.md
├── hip_replacement.md
├── surgical_case.md
└── escalation/                # Agent 5 tier criteria, added 25 Aug 2026
    ├── _FORMAT.md             #   format spec + what a reviewer signs
    ├── universal.md           #   diagnosis-independent tiers
    ├── heart_failure.md       #   per-diagnosis additions
    ├── copd.md
    ├── diabetes.md
    ├── hip_replacement.md
    └── surgical_case.md
```

**The escalation templates are INERT until a physician signs them.** A
template governs output only when its sign-off block names a real reviewer AND
a real date; `[Pending - ...]` parses as unsigned. All six ship unsigned, so
Agent 5 generates all three tiers exactly as it always has. Loader and
verifier: `dischargeiq/utils/escalation_templates.py`. Status:
`python scripts/escalation_template_status.py`.

## Agent 1 JSON output schema (LOCKED - do not change casually)

This is the contract between Agent 1 and all downstream agents.
Agent 1 must NEVER fabricate or infer values. If a field is not in the
document, return null. For list fields, return [] not null.
```python
from pydantic import BaseModel
from typing import Optional, List

class Medication(BaseModel):
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    status: Optional[str] = None  # new | changed | continued | discontinued

class FollowUpAppointment(BaseModel):
    provider: Optional[str] = None
    specialty: Optional[str] = None
    date: Optional[str] = None
    reason: Optional[str] = None

class ExtractionOutput(BaseModel):
    patient_name: Optional[str] = None
    discharge_date: Optional[str] = None
    primary_diagnosis: str
    secondary_diagnoses: List[str] = []
    procedures_performed: List[str] = []
    medications: List[Medication] = []
    follow_up_appointments: List[FollowUpAppointment] = []
    activity_restrictions: List[str] = []
    dietary_restrictions: List[str] = []
    red_flag_symptoms: List[str] = []
    discharge_condition: Optional[str] = None
    extraction_warnings: List[str] = []
```

## Pipeline response model
```python
class MissedConcept(BaseModel):
    question: str
    answered_by_doc: bool
    gap_summary: str
    severity: Literal["critical", "moderate", "minor"]

class PatientSimulatorOutput(BaseModel):
    missed_concepts: list[MissedConcept]
    overall_gap_score: int          # 0–10; higher = more gaps
    simulator_summary: str
    fk_grade: float
    passes: bool                    # vs internal FK threshold of 8.0

class PipelineResponse(BaseModel):
    extraction: ExtractionOutput
    diagnosis_explanation: str
    medication_rationale: str
    recovery_trajectory: str
    escalation_guide: str
    fk_scores: dict
    extraction_warnings: list
    pipeline_status: str            # "complete" | "complete_with_warnings" | "partial" | "rejected"
    rejection_reason: Optional[str] = None  # set only when status == "rejected" (router gate)
    patient_simulator: Optional[PatientSimulatorOutput] = None  # None if Agent 6 skipped/failed
```

## Five target diagnoses

All agents are tested against these 5 conditions:
- Heart failure (guideline: ACC/AHA)
- COPD (guideline: GOLD 2024)
- Diabetes management (guideline: ADA 2024)
- Hip replacement (guideline: AAOS)
- Surgical case / laparoscopic (guideline: ACC/ACS perioperative)

## Hard rules - never violate these

1. Agent 1 never fabricates or guesses a field value. null is always safer
   than a wrong answer.
2. Agents 2, 3, 4, 5 never tell the patient to stop or change a medication.
3. Agent 5 (Escalation) is safety-critical. Every output must be read
   manually before marking done. Zero ambiguous language ("may need",
   "consider calling") is acceptable.
4. Every agent text output must be run through fk_check() from utils/scorer.py.
   Target: Flesch-Kincaid grade ≤ 6.0 on all outputs.
5. Never commit API keys or .env files. .env must be in .gitignore.
6. No identifiable patient data, ever. The test corpus is de-identified
   third-party material (MTSamples transcriptions with identifiers removed);
   it may live in this repo only while the repo is PRIVATE.
7. The pipeline must never crash on a bad document. Use try/except per agent
   and set pipeline_status = "partial" with a fallback message if any agent
   fails.

## FK scorer utility
```python
# utils/scorer.py - three public functions

def fk_score(text: str) -> float: ...          # raw FK grade via textstat
def fk_check(text: str, threshold: float = 6.0) -> dict: ...  # {fk_grade, passes, threshold}
def log_fk_score(document_id: str, agent: str, fk_result: dict) -> None: ...
    # Appends one row to evaluation/fk_log.csv under threading.Lock.
    # agent examples: "agent3_medication", "agent4_recovery", "agent5_escalation"
    # All agents 3–5 call log_fk_score() - do NOT write CSV logic in agent files.
```

Call fk_check() on every agent text output. If score > 6.0, the system
prompt for that agent needs revision - add instructions like:
"Use short sentences. Maximum 15 words per sentence. Avoid medical jargon."

## Claude API call pattern
```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=2000,
    system=system_prompt_string,
    messages=[{"role": "user", "content": user_content_string}]
)

output_text = response.content[0].text.strip()
```

Always strip markdown fences from JSON responses before parsing:
```python
raw = raw.replace("```json", "").replace("```", "").strip()
```

## FastAPI endpoint

The main pipeline endpoint is POST /analyze
It accepts a PDF file upload and returns a PipelineResponse as JSON.
```python
@app.post("/analyze")
async def analyze_discharge(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = run_pipeline(tmp_path)
        return result.dict()
    finally:
        os.unlink(tmp_path)
```

## Test scripts

- `tests/test_agent1.py` - runs Agent 1 on all PDFs in `test-data/`, prints pass/fail (manual: `python tests/test_agent1.py` from repo root).
- `tests/test_agents_1_2.py` - end-to-end Agents 1 and 2 on `test-data/` (manual: `python tests/test_agents_1_2.py`).
- `tests/manual/test_claude_api.py` - Anthropic API key smoke (manual: `python tests/manual/test_claude_api.py`).
- `tests/manual/test_neon_db.py` - Neon/Postgres connectivity smoke (manual: `python tests/manual/test_neon_db.py`).

Automated pytest suites live under `dischargeiq/tests/` (see README). Hard gate: Agent 1 must pass 8/10 test documents before Agent 2 development starts.

## Neon PostgreSQL schema
```sql
CREATE TABLE discharge_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    document_hash VARCHAR(64) NOT NULL,
    primary_diagnosis VARCHAR(255),
    discharge_date VARCHAR(50),
    pipeline_status VARCHAR(20),
    extracted_fields JSONB,
    fk_scores JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

Never store full PDF text or free-text agent outputs in the database.
Only store structured fields, hashes, and metadata.

## Historical planning note (superseded)

Older milestone breakdowns appeared below in prior edits of this file.
**Current priorities** are **not** tracked in CLAUDE.md; use team planning tools
and the section **[Current project status (detailed)](#current-project-status-detailed--for-ai-assistants)** above.

## What a good Agent 2 output looks like (example for heart failure)

"Your main diagnosis is heart failure. This means your heart was not
pumping blood as well as it should. Blood backed up in your lungs, which
made it hard to breathe and caused swelling in your legs. During your
stay, doctors gave you medicine to remove the extra fluid from your body.
At home, you will take pills to help your heart pump better. Most people
start to feel better in 2 to 4 weeks."

FK score on that paragraph: ~5.1. Short sentences, no jargon, plain language.

## AI Agent Rules - Read before doing anything

These rules apply to every AI agent working in this repo.
No exceptions. No overrides.

### Git and commits

- Do NOT commit, stage, or push by default. Suggest what to commit and why,
  and let the human decide.
- The exception is an explicit, in-session instruction to commit ("commit
  this", "do incremental commits and push"). That instruction overrides the
  default for that session only; it does not carry over to the next one.
- NEVER open a pull request, and never push to a branch you were not told to
  push to. `main` and the LOF-facing branches are the human's to move.
- When committing under instruction: small, single-purpose commits, no
  `Co-Authored-By` trailer, and no AI attribution of any kind (see
  Authorship below - that rule has no exception).
- Never commit `.env`, keys, device backups, or corpus data. Check
  `git status` before every commit rather than staging everything.

### Authorship and identity

- NEVER add yourself as a co-author, contributor, or reviewer in any commit message,
  file header, docstring, or comment.
- Do not include lines like "Generated by Claude" or "AI-assisted" anywhere in the code.
- All code is authored by the human team. You are a tool, not a contributor.

### Code quality standard

Write code as a senior engineer with a Master's in Computer Science would write it -
not a student, not a script generator. Every file you produce must meet these standards:

**Clarity**
- Every function has a docstring explaining what it does, its parameters,
  what it returns, and any exceptions it can raise.
- Every non-obvious line has an inline comment explaining why, not just what.
- Variable and function names are descriptive. No single-letter names except
  loop counters. No abbreviations unless they are universally understood (e.g. db, api, cfg).

**Structure**
- One responsibility per function. If a function does more than one thing, split it.
- No function longer than 40 lines. If it is longer, it needs to be refactored.
- Imports are grouped: standard library first, then third-party, then local.
  A blank line separates each group.
- No dead code, no commented-out blocks, no TODO left in production paths.

**Error handling**
- Every external call (Claude API, database, file I/O) is wrapped in try/except.
- Errors are logged with enough context to debug. Never silently swallow exceptions.
- Use specific exception types, not bare `except Exception`.

**Comments for whoever reads this next**
- At the top of every file, write a 3–5 line module-level docstring explaining
  what the file does, which agent or component it belongs to, and any dependencies
  the reader should know about before editing.
- At every integration point between agents (e.g. where Agent 1 output is passed
  to Agent 2), leave a comment explaining the data contract:
  what format is expected, what fields are required, and what happens if they are missing.

**Example of the comment style expected:**
```python
def run_extraction_agent(pdf_text: str) -> ExtractionOutput:
    """
    Agent 1: Extracts structured fields from raw discharge document text.

    Sends the PDF text to Claude with a strict extraction system prompt.
    Validates the response against the ExtractionOutput Pydantic model.
    Returns the validated model on success.

    Args:
        pdf_text: Raw text extracted from the discharge PDF via pdfplumber.

    Returns:
        ExtractionOutput: Validated Pydantic model containing all extracted fields.
                          Fields not found in the document are returned as None or [].

    Raises:
        json.JSONDecodeError: If Claude returns malformed JSON despite the prompt.
        ValidationError: If the JSON does not match the ExtractionOutput schema.

    Note:
        This is the HARD GATE agent. Do not proceed to Agent 2 until this
        function passes on 8/10 test documents. The schema it returns is the
        contract for all downstream agents - never change field names without
        a deliberate decision, recorded in the commit, that updates every
        downstream consumer in the same change.
    """
```

### What to do instead of committing

When you finish writing or modifying a file:
1. Print a clear summary of what you changed and why.
2. List which files were created or modified.
3. Note any decisions you made that the team should review.
4. Then stop. Wait for the human to review and commit.