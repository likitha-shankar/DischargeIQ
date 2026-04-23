# DischargeIQ — Project Context for AI Agents

## What this project is

DischargeIQ is a multi-agent AI system that reads hospital discharge PDFs
and generates plain-language patient education content. A patient uploads
a photo or PDF of their discharge document and receives five sections of
output written at a 6th grade reading level:

1. What Happened to You (diagnosis explanation)
2. Your Medications Explained (per-drug rationale)
3. Your Recovery Timeline (week-by-week guide)
4. Warning Signs: When to Get Help (three-tier escalation decision tree)
5. Your Discharge Summary Details (structured extraction)

This is a graduate course project (CS 595, IIT Chicago, Spring 2026).
It targets the LOF Patient Engagement pillar. The primary use case is
post-discharge health literacy for patients who do not understand their
discharge documents.

## Current project status (detailed) — for AI assistants

**Last reviewed:** April 2026. Treat this section as the source of truth for
“what is happening now.” Older sections below (e.g. sprint dates) may be stale.

### Where the product stands

- **End-to-end pipeline is implemented:** PDF upload → Agent 1 extraction →
  Agents 2–5 (diagnosis, medication, recovery, escalation) → FK checks →
  `PipelineResponse` JSON. Orchestration lives in `dischargeiq/pipeline/orchestrator.py`.
- **Primary surface for demos:** **Streamlit** (`streamlit_app.py`), started by
  `./start.sh` (or `start.bat` on Windows). Default URL: http://127.0.0.1:8501.
- **Backend:** FastAPI in `dischargeiq/main.py`, typically http://127.0.0.1:8000.
- **Failure mode:** The pipeline is designed to return **`pipeline_status` of
  `"complete"`, `"complete_with_warnings"`, or `"partial"`** (not to crash on bad PDFs or
  LLM failures). `"partial"` runs may occur when an agent fails, rate limits hit (429),
  timeouts occur, or keys are missing. `"complete_with_warnings"` means all agents ran
  but extraction completeness warnings were raised.

### LLM and environment configuration

- **Single provider for all five agents:** Every agent reads **`LLM_PROVIDER`**
  (default **`openrouter`**) via `get_llm_client()` in `dischargeiq/utils/llm_client.py`
  (Agent 1 / Agent 2) or `_get_client()` in agents 3–5. There is **no** split where
  only Agent 1 uses OpenRouter and 2–5 always use Anthropic—switching `.env` switches
  **every** agent. Token cost jumps when moving to **`anthropic`** for eval.
- **Anthropic model ID:** Use a **dated** Sonnet id (e.g. **`claude-sonnet-4-20250514`**).
  Undated aliases can **404**. Set `LLM_MODEL` explicitly in `.env` for Week 5.
- Keys per `.env.example`: `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, **`ANTHROPIC_API_KEY`**
  (required when `LLM_PROVIDER=anthropic`), optional `OLLAMA_BASE_URL`. Missing keys
  raise **`ValueError`** with a clear message from `require_provider_api_key()` rather
  than a raw **`KeyError`**.
- **`DATABASE_URL`** supports Neon PostgreSQL (history / persistence) where wired;
  local development may work without DB for core `/analyze` paths—confirm in code
  paths if debugging save failures.

### HTTP API (FastAPI)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness |
| POST | `/analyze` | Multipart PDF upload; runs full pipeline |
| GET | `/pdf/{session_id}` | Retrieve stored PDF bytes for session (used with Streamlit viewer) |
| POST | `/chat` | Grounded chat answer. Body: `message`, `session_id`, `pipeline_context` (CORS enabled for Streamlit origins) |

### Frontend and tooling

- **Streamlit** is the main MVP UI; it talks to the API (including `/chat` with CORS).
- **iOS / SwiftUI client:** Development is **on hold** for the shared repo.
  The entire **`ios/`** directory is listed in **`.gitignore`** so it stays
  **local-only** until the team turns it back on. Do not assume teammates have
  `ios/` in their clone from Git.

### Testing

Notable tests under `dischargeiq/tests/`:

- `test_integration_hallucination.py` — integration / hallucination gates (see README).
- `test_api_guardrails.py` — API behavior and guardrails.
- `test_resilience_hardening.py` — retries, OpenRouter error paths.
- `test_all_corpus_smoke.py` — corpus smoke coverage.

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
- **Multi-key setup:** New contributors often forget one of `OPENROUTER_*` /
  `OPENAI_*` / `ANTHROPIC_*` depending on which path they test.
- **No iOS in Git:** Any Swift work lives only in local `ios/` until `.gitignore`
  changes.
- **No automatic LLM cross-failover:** If `anthropic` is down, agents 2–5 paths
  fail together; the API still returns **partial** with empty sections. Streamlit
  now shows **section-level warnings**; a full provider fallback is not wired.

## Team (Plan B assignments)

- Likitha — Team Lead, Backend + LLM (owns DIS-1, DIS-5, DIS-13, DIS-14, DIS-23)
- Suchithra — Strong, Frontend + LLM (owns DIS-2, DIS-9, DIS-12, DIS-16, DIS-22, DIS-24)
- Deepesh — Strong, Anything (owns DIS-4, DIS-6, DIS-8, DIS-10, DIS-17, DIS-21)
- Rushi — Weak, Anything (owns DIS-7, DIS-15, DIS-19)
- Manusha — Weak, Data Infra (owns DIS-3, DIS-18)

## Tech stack

- Backend: FastAPI + Python 3.11+
- LLM: Configurable — all agents share `LLM_PROVIDER` (OpenAI-compatible client
  and/or native Anthropic SDK in agents 3–5 when `LLM_PROVIDER=anthropic`).
  Default Sonnet id for Anthropic path: `claude-sonnet-4-20250514` (see `llm_client.py`).
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
├── .env.example               # ANTHROPIC_API_KEY= and DATABASE_URL=
├── .gitignore                 # must include .env
├── agents/
│   ├── extraction_agent.py    # Agent 1
│   ├── diagnosis_agent.py     # Agent 2
│   ├── medication_agent.py    # Agent 3
│   ├── recovery_agent.py      # Agent 4
│   └── escalation_agent.py    # Agent 5
├── models/
│   ├── extraction.py          # Pydantic ExtractionOutput model
│   └── pipeline.py            # Pydantic PipelineResponse model
├── pipeline/
│   └── orchestrator.py        # Wires all 5 agents together
├── prompts/
│   ├── agent1_system_prompt.txt
│   ├── agent2_system_prompt.txt
│   ├── agent3_system_prompt.txt
│   ├── agent4_system_prompt.txt
│   ├── agent5_system_prompt.txt
│   └── llm_judge_prompt.txt
├── utils/
│   ├── scorer.py              # fk_score() and fk_check()
│   └── warnings.py            # assess_extraction_completeness()
├── db/
│   └── history.py             # save_discharge_history(), get_history_for_session()
├── templates/                 # Clinician-reviewed diagnosis templates (markdown)
│   ├── heart_failure.md
│   ├── copd.md
│   ├── diabetes.md
│   ├── hip_replacement.md
│   └── surgical_case.md
├── test-data/                 # 10 synthetic discharge PDFs (2 per diagnosis)
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

## Agent 1 JSON output schema (LOCKED — do not change without team sign-off)

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
class PipelineResponse(BaseModel):
    extraction: ExtractionOutput
    diagnosis_explanation: str
    medication_rationale: str
    recovery_trajectory: str
    escalation_guide: str
    fk_scores: dict
    extraction_warnings: list
    pipeline_status: str  # "complete" | "complete_with_warnings" | "partial" — never raises an unhandled exception
```

## Five target diagnoses

All agents are tested against these 5 conditions:
- Heart failure (guideline: ACC/AHA)
- COPD (guideline: GOLD 2024)
- Diabetes management (guideline: ADA 2024)
- Hip replacement (guideline: AAOS)
- Surgical case / laparoscopic (guideline: ACC/ACS perioperative)

## Hard rules — never violate these

1. Agent 1 never fabricates or guesses a field value. null is always safer
   than a wrong answer.
2. Agents 2, 3, 4, 5 never tell the patient to stop or change a medication.
3. Agent 5 (Escalation) is safety-critical. Every output must be read
   manually before marking done. Zero ambiguous language ("may need",
   "consider calling") is acceptable.
4. Every agent text output must be run through fk_check() from utils/scorer.py.
   Target: Flesch-Kincaid grade ≤ 6.0 on all outputs.
5. Never commit API keys or .env files. .env must be in .gitignore.
6. No real patient data. All test documents must be synthetic or
   de-identified.
7. The pipeline must never crash on a bad document. Use try/except per agent
   and set pipeline_status = "partial" with a fallback message if any agent
   fails.

## FK scorer utility
```python
# utils/scorer.py
import textstat

def fk_score(text: str) -> float:
    return textstat.flesch_kincaid_grade(text)

def fk_check(text: str, threshold: float = 6.0) -> dict:
    score = fk_score(text)
    return {
        "fk_grade": round(score, 2),
        "passes": score <= threshold,
        "threshold": threshold
    }
```

Call fk_check() on every agent text output. If score > 6.0, the system
prompt for that agent needs revision — add instructions like:
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

- test_agent1.py — runs Agent 1 on all PDFs in /test-data/, prints pass/fail
- test_agents_1_2.py — end-to-end Agents 1 and 2
- test_agents_1_2_3.py — end-to-end Agents 1, 2, and 3
- test_full_pipeline.py — all 5 agents, logs P95 time, must be under 30s

Hard gate: Agent 1 must pass 8/10 test documents before Agent 2 development starts.

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

## Historical sprint note (superseded)

Early sprint breakdowns (DIS-* tickets, week-1 targets) appeared below in prior
edits of this file. **Current priorities** are **not** tracked in CLAUDE.md; use
team planning tools and the section **[Current project status (detailed)](#current-project-status-detailed--for-ai-assistants)** above. DIS-* IDs in the team list are still useful ownership hints.

## What a good Agent 2 output looks like (example for heart failure)

"Your main diagnosis is heart failure. This means your heart was not
pumping blood as well as it should. Blood backed up in your lungs, which
made it hard to breathe and caused swelling in your legs. During your
stay, doctors gave you medicine to remove the extra fluid from your body.
At home, you will take pills to help your heart pump better. Most people
start to feel better in 2 to 4 weeks."

FK score on that paragraph: ~5.1. Short sentences, no jargon, plain language.

## AI Agent Rules — Read before doing anything

These rules apply to every AI agent working in this repo.
No exceptions. No overrides.

### Git and commits

- NEVER run `git commit`, `git push`, or `git add` for any reason.
- NEVER stage files. NEVER create a commit message. NEVER initiate a pull request.
- Only suggest what to commit and why. The human decides when and what gets committed.
- If you think something is ready to commit, say so in a comment — do not act on it.

### Authorship and identity

- NEVER add yourself as a co-author, contributor, or reviewer in any commit message,
  file header, docstring, or comment.
- Do not include lines like "Generated by Claude" or "AI-assisted" anywhere in the code.
- All code is authored by the human team. You are a tool, not a contributor.

### Code quality standard

Write code as a senior engineer with a Master's in Computer Science would write it —
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

**Comments for teammates**
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
        contract for all downstream agents — never change field names without
        team sign-off.
    """
```

### What to do instead of committing

When you finish writing or modifying a file:
1. Print a clear summary of what you changed and why.
2. List which files were created or modified.
3. Note any decisions you made that the team should review.
4. Then stop. Wait for the human to review and commit.