# DischargeIQ — Course Project Definition

**Course:** CS 595 Med Informatics AI: SeeDoBuild, Spring 2026  
**Institution:** Illinois Institute of Technology, Chicago  
**Sponsor:** Leap of Faith Health Tech  
**Team:** MedSynapse  
**Project ID:** CS595-2026-DischargeIQ  
**LOF Pillar:** Patient Engagement

---

## Section 1: Project Identity

| Field         | Value                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------|
| Project ID    | CS595-2026-DischargeIQ                                                                             |
| Team name     | MedSynapse                                                                                         |
| Course        | CS 595 Med Informatics AI: SeeDoBuild, Spring 2026                                                 |
| Sponsor       | Leap of Faith Health Tech                                                                          |
| LOF Pillar    | Patient Engagement                                                                                 |
| Sub-domain    | Post-Acute Care — Discharge Comprehension                                                          |
| Team Lead     | Likitha Shankar                                                                                    |
| Team Members  | Suchithra Rajkumar, Deepesh Kumar Appar Senthilkumar, Manusha Boorgula, Rushi Eshwar Reddy Neelam  |

---

## Section 2: Problem Statement

Hospital discharge documents are written at an average 12th-grade reading level.
The average patient reads at a 6th-grade level. This gap causes preventable
readmissions, medication errors, and post-discharge confusion. Physicians average
2–3 minutes on discharge instructions at the point of care. There is no widely
adopted tool that converts a discharge PDF into verified, plain-language patient
education content at the point of discharge.

The consequences are measurable: hospital readmission rates remain above 15% for
conditions such as heart failure, COPD, and hip replacement — conditions where
comprehension of discharge instructions is directly tied to outcome. Patients who
cannot understand their medication list, warning signs, or follow-up requirements
are at highest risk.

---

## Section 3: NABC Analysis

### Need

A patient leaves the hospital with a PDF discharge summary written for a
physician audience. The document contains the information needed for safe
recovery — medication instructions, warning signs, follow-up appointments,
dietary and activity restrictions — but it is not written for the patient. No
automated system currently converts that document into plain language, verifies
that it is actually readable, or identifies what the document fails to explain.

### Approach

DischargeIQ is a six-agent AI pipeline. A patient uploads their discharge PDF
to the Streamlit dashboard (`streamlit_app.py`). The pipeline:

1. **Agent 1** (`agents/extraction_agent.py`) — Extracts structured data from
   the PDF using pdfplumber and an LLM with strict extraction rules: diagnosis,
   medications (with dose, frequency, status), follow-up appointments (with
   source page citations), activity restrictions, dietary restrictions, red-flag
   symptoms, discharge condition, and patient metadata. Never fabricates fields;
   returns null or [] when a field is absent.

2. **Agent 2** (`agents/diagnosis_agent.py`) — Generates a plain-language
   explanation of the primary diagnosis and procedures, targeting 6th-grade
   reading level. Uses Flesch-Kincaid scoring via `utils/scorer.py`; retries
   once if FK grade exceeds 6.5.

3. **Agent 3** (`agents/medication_agent.py`) — Explains each medication's
   purpose, observable effects, expected side effects, and emergency symptoms
   in four points per drug. Handles discontinued medications. Includes verbatim
   safety language: "do not stop this medication without calling your doctor."

4. **Agent 4** (`agents/recovery_agent.py`) — Generates a week-by-week
   recovery guide structured by time period (Week 1, Week 2, Weeks 3–4, When
   to expect improvement). Incorporates every activity and dietary restriction
   extracted by Agent 1 without omission.

5. **Agent 5** (`agents/escalation_agent.py`) — Generates a three-tier
   escalation decision tree: CALL 911 IMMEDIATELY, GO TO THE ER TODAY, and
   CALL YOUR DOCTOR. Assigns every red-flag symptom to exactly one tier.
   Safety-critical; all outputs must be manually reviewed before clinical use.

6. **Agent 6** (`agents/patient_simulator_agent.py`) — Simulates a confused
   patient asking 6–8 questions a real patient would ask after reading the
   document. Scores each question: answered by doc (yes/no), gap summary,
   severity (critical / moderate / minor). Produces an overall gap score 0–10.
   Also generates per-item caregiver questions for each medication, appointment,
   and warning sign.

All agents run through `pipeline/orchestrator.py`. The orchestrator extracts
safety context from the raw PDF text (emergency language phrases), wraps each
agent in error handling, sets `pipeline_status` to `"complete"`,
`"complete_with_warnings"`, or `"partial"`, saves to Neon PostgreSQL, and
returns a `PipelineResponse` Pydantic model. Total runtime is typically under
90 seconds on Anthropic Haiku.

The patient also has a grounded chat panel. Every question is answered strictly
from the discharge document; answers cite the source page. The chat calls
`POST /chat` on the FastAPI backend.

### Benefits

What DischargeIQ produces for a patient:

- **Plain-language summary in six sections** — each verified by Flesch-Kincaid
  readability scoring (target: FK grade ≤ 6.0 for Agents 2–5).
- **Source citations** — every follow-up appointment and extracted medication
  links back to the page number in the original PDF.
- **A comprehension gap audit** — before the patient sees the summary, Agent 6
  has already identified which questions go unanswered, rated by clinical
  severity, giving care coordinators a prioritized action list.
- **A grounded chatbot** — patients can ask follow-up questions and receive
  answers tied to their specific document.
- **Caregiver-ready questions** — per-item questions formatted for the patient
  to ask their doctor or care coordinator at follow-up.

### Competition

**Epic MyChart patient portal**
Patients view discharge summaries in a portal, but summaries are written in
clinical language. No plain-language conversion, no diagnosis explanation, no
gap detection — document delivery without comprehension support.

**Nuance DAX and similar ambient AI scribes**
Transcribe and summarize physician encounters. Physician-facing by design;
produce clinical documentation, not patient education.

**General-purpose LLMs (ChatGPT, Gemini, etc.)**
Answer medical questions but have no document grounding, no FK readability
gate, no structured extraction, and unchecked hallucination risk.

**Paper discharge instructions (current standard of care)**
Printed sheet given at discharge. No comprehension layer, no plain-language
conversion, no follow-up support.

> **Key differentiator:** DischargeIQ is the only system that combines
> structured discharge PDF extraction, plain-language generation with FK
> readability gating, and an AI patient simulator that audits the document
> for comprehension gaps before the patient sees it.

---

## Section 4: System Architecture

### Pipeline Flow

```
Patient PDF Upload
      │
      ▼
Agent 1 (extraction_agent.py)
      │  ExtractionOutput (JSON)
      ▼
┌─────────────────────────────────────────┐
│  Agent 2   Agent 3   Agent 4   Agent 5  │  (sequential; could be parallelized)
│  Diagnosis  Meds    Recovery  Escalation│
└─────────────────────────────────────────┘
      │
      ▼
Agent 6 (patient_simulator_agent.py)
      │  PatientSimulatorOutput (non-fatal)
      ▼
PipelineResponse → FastAPI → Streamlit
```

### Component Map

| Component                  | File                                      | Port          |
|----------------------------|-------------------------------------------|---------------|
| Orchestrator               | `dischargeiq/pipeline/orchestrator.py`    | —             |
| FastAPI backend            | `dischargeiq/main.py`                     | 8000          |
| Streamlit frontend         | `streamlit_app.py`                        | 8501          |
| Flutter mobile (on hold)   | `dischargeiq_mobile/`                     | 55497 (web)   |
| Neon PostgreSQL            | `dischargeiq/db/`                         | (external)    |

### LLM Configuration

All agents share a single LLM provider set by `LLM_PROVIDER` in `.env`.
Provider routing is in `dischargeiq/utils/llm_client.py`. Supported providers:
`anthropic` (default), `openrouter`, `openai`, `ollama`. Default model:
`claude-haiku-4-5-20251001`. Override with `LLM_MODEL=claude-sonnet-4-20250514`
for higher quality.

### Readability Gating

Every agent text output passes through `utils/scorer.py`:

```python
def fk_check(text: str, threshold: float = 6.0) -> dict:
    score = fk_score(text)
    return {"fk_grade": round(score, 2), "passes": score <= threshold}
```

Agents 2–5 gate at FK ≤ 6.0. Agent 6 gates at FK ≤ 8.0 (gap summaries are
more technical). FK results are logged to `dischargeiq/evaluation/fk_log.csv`
and returned in `PipelineResponse.fk_scores`.

### Database Schema

One table in Neon PostgreSQL (`dischargeiq/db/schema.sql`):

```
discharge_history (
    session_id, document_hash, primary_diagnosis, discharge_date,
    pipeline_status, extracted_fields JSONB, fk_scores JSONB, created_at
)
```

Stores structured metadata only. No free-text agent outputs. No raw PDF bytes.

---

## Section 5: Product Framing

DischargeIQ is a **comprehension and education layer**, not clinical decision
support. It does not diagnose, prescribe, or make clinical recommendations.

**Human-in-the-loop is explicit:**
- Agent 6 surfaces missed concepts; a human (care coordinator, nurse, patient's
  care team member) reviews the AI Review tab and decides what to act on.
- Agent 5's escalation tiers must be manually reviewed before clinical use;
  zero ambiguous language ("may need to call") is acceptable.
- The chat panel explicitly tells the patient that answers are from their
  discharge document and to consult their care team for medical advice.

**Two-box model with TheraCareAI:**
- DischargeIQ is Box 1: comprehension at discharge.
- TheraCareAI is Box 2: adherence tracking in the weeks following discharge.
- DischargeIQ's structured `ExtractionOutput` (medications, follow-up
  appointments, restrictions) is the data contract between the two systems.
  Any integration must not break the `ExtractionOutput` schema without team
  sign-off.

---

## Section 6: Scope

### In Scope (implemented and verified)

- PDF upload and pdfplumber text extraction
- Structured extraction of diagnosis, medications, appointments, restrictions,
  red flags (Agent 1)
- Plain-language diagnosis explanation with FK gating (Agent 2)
- Per-drug medication rationale with safety language (Agent 3)
- Week-by-week recovery guide (Agent 4)
- Three-tier escalation decision tree (Agent 5)
- AI patient simulator with gap score and severity labels (Agent 6)
- Grounded patient chatbot with source citations
- Streamlit dashboard with six tabs
- FastAPI backend with progress tracking and in-memory PDF store
- Neon PostgreSQL persistence (write path)
- FK readability scoring across all agents
- LLM judge evaluation harness (`evaluation/run_judge.py`)
- 16+ automated pytest tests including safety, resilience, and hallucination gates

### Out of Scope

- Clinical decision support or differential diagnosis
- EHR integration or write-back (Epic, Cerner, etc.)
- HIPAA compliance hardening for production use with real patient data
- Doctor-facing or clinician portal
- Real patient data — all test documents are synthetic
- Multi-turn conversation history persistence on the backend
- History read-back in the Streamlit UI (DB write path only)
- Authentication or role-based access
- Mobile clients (iOS SwiftUI and Flutter are paused and gitignored)

---

## Section 7: Evaluation Framework

### FK Readability Scoring

Every agent text output is scored by `utils/scorer.py` using `textstat.flesch_kincaid_grade()`.

| Agent                 | FK Threshold | Notes                                          |
|-----------------------|--------------|------------------------------------------------|
| Agent 2 (Diagnosis)   | 6.0          | Retries once if FK > 6.5                       |
| Agent 3 (Medication)  | 6.0          | —                                              |
| Agent 4 (Recovery)    | 6.0          | —                                              |
| Agent 5 (Escalation)  | 6.0          | Safety-critical; manual review still required  |
| Agent 6 (Simulator)   | 8.0          | Gap summaries tolerate slightly higher grade   |

Results logged to `dischargeiq/evaluation/fk_log.csv` on every run.

### LLM-as-Judge

`evaluation/run_judge.py` — Anthropic-powered evaluator scores each agent
output on four dimensions (clinical accuracy 1–5, plain language 1–5,
completeness 1–5, actionability 1–5) plus a pass/fail safety gate. Results
saved to `evaluation/judge_results.json`. Judge prompt at
`dischargeiq/prompts/llm_judge_prompt.txt`.

### Test Fixtures

`dischargeiq/tests/fixtures/` — Adversarial synthetic PDFs including cases with
no medications, abbreviated formats, ER discharge sheets, and multi-condition
documents. The fixture builder is at
`dischargeiq/tests/fixtures/build_real_world_fixtures.py`.

`test-data/` — 10 synthetic discharge PDFs (2 per diagnosis): heart failure,
COPD, diabetes, hip replacement, surgical case.

### Test Suite Coverage

| Test file                              | What it covers                                                    |
|----------------------------------------|-------------------------------------------------------------------|
| `test_integration_hallucination.py`    | 8 adversarial cases; gate fails if any agent fabricates a field   |
| `test_all_corpus_smoke.py`             | Full 10-PDF corpus; FK pass rates; marked `@pytest.mark.slow`     |
| `test_api_guardrails.py`               | Upload validation, CORS, status codes                             |
| `test_agent3_safety.py`                | Agent 3 safety language presence                                  |
| `test_agent5_safety.py`                | Agent 5 tier assignment correctness                               |
| `test_resilience_hardening.py`         | 429 rate limit handling, timeout handling, partial runs           |
| `test_diagnosis_agent.py`              | Agent 2 FK scoring + retry on high FK                             |
| `test_chat_grounding.py`               | Chat stays grounded; source page detection                        |

---

## Section 8: Open Deployment Questions

| Question                       | Current state                                                                                                                           |
|--------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------|
| **Internet requirement**       | All LLM calls go to an external provider. An Ollama path exists for offline use but has not been tested under demo conditions.          |
| **Session persistence**        | PDFs stored in process memory (LRU cap: 50). Server restart clears all sessions. DB write persists metadata only — not PDF bytes.       |
| **Authentication**             | No user login in MVP. Any user with the URL can upload a PDF. Auth required before any real patient data is used.                       |
| **End-to-end patient flow**    | Open Streamlit (http://127.0.0.1:8501), upload PDF, wait ~60–90 s, browse six tabs, use chat. No account, no session recovery after restart. |

---

## Section 9: Future Roadmap

**TheraCareAI integration**
DischargeIQ's `ExtractionOutput` (medications, follow-up appointments,
restrictions) is the structured handoff to TheraCareAI's adherence pipeline.
Integration point: `POST /analyze` response — TheraCareAI consumes
`extraction.medications` and `extraction.follow_up_appointments` to initialize
adherence reminders. DischargeIQ is Box 1; TheraCareAI is Box 2.

**Post-acute care pilot — 30-day readmission reduction**
Deploy at a single LOF partner site targeting heart failure and COPD.
Measure patient comprehension pre/post (modified REALM-SF), care coordinator
workload, and 30-day readmission rate vs control group.

**Parallelize Agents 2–5**
Agents 2–5 are independent after Agent 1. Running them concurrently
(`asyncio.gather`) would cut pipeline latency by ~3×. No changes needed to
the agents themselves — orchestrator wiring only.

**History read path**
`get_history_for_session()` is implemented in `dischargeiq/db/history.py` but
not wired. Adding `GET /history/{session_id}` + a Streamlit history tab gives
patients access to past summaries.

---

## Section 10: Tech Stack and Versions

See `requirements.txt` for pinned versions. Summary:

| Layer                | Technology          | Version                      |
|----------------------|---------------------|------------------------------|
| Backend framework    | FastAPI             | >=0.110.0                    |
| ASGI server          | Uvicorn             | >=0.29.0                     |
| Frontend             | Streamlit           | >=1.32.0                     |
| Mobile (on hold)     | Flutter / Dart      | >=3.3.0 SDK                  |
| LLM (default)        | Anthropic Haiku     | claude-haiku-4-5-20251001    |
| LLM (high quality)   | Anthropic Sonnet    | claude-sonnet-4-20250514     |
| LLM SDK              | anthropic           | >=0.25.0                     |
| OpenAI-compat SDK    | openai              | >=1.0.0                      |
| PDF extraction       | pdfplumber          | >=0.11.0                     |
| Readability scoring  | textstat            | >=0.7.13                     |
| Data validation      | Pydantic v2         | >=2.0.0                      |
| Database             | Neon PostgreSQL     | — (external service)         |
| DB driver            | asyncpg             | >=0.29.0                     |
| Runtime              | Python              | 3.11+                        |
| Test runner          | pytest              | >=8.0,<9.0                   |

---

## Section 11: Risks

### Hallucination in Plain-Language Generation

Agents 2–5 generate free text from structured extraction fields. There is a risk
that an LLM produces plausible-sounding but incorrect clinical content that is
not grounded in the discharge document. Mitigations in place: Agent 1 extracts
only what is explicitly in the document (no inference); Agents 2–5 are given
only the specific fields they need (via `utils/extraction_scope.py`); the
hallucination integration test (`test_integration_hallucination.py`) gates on
eight adversarial cases.

### FK Scoring Passing Clinically Unsafe Text

A sentence can score below FK grade 6.0 while still being clinically ambiguous
or incomplete. FK measures sentence complexity, not accuracy. A short, simple
sentence can be factually wrong. FK gating is a necessary but not sufficient
quality check. Agent 5 (escalation) requires manual review for this reason.

### No Authentication in MVP

The MVP has no user login. Anyone with the URL can upload a PDF. For development
and demos with synthetic PDFs this is acceptable. For any deployment where real
patient data might be used, authentication and access control must be added before
HIPAA applicability even needs to be assessed.

### Adversarial and Malformed PDFs

Scanned PDFs (image-only, no selectable text) return empty pdfplumber output.
Agent 1 flags these as extraction warnings, but the downstream agents receive
only `primary_diagnosis = "unknown"` or similar. Very large PDFs (>100 pages)
may hit the 300-second orchestrator timeout and return a partial result. PDFs
with unusual structure (tables-only, forms, non-standard encoding) may produce
low-quality extraction that all downstream agents inherit.

### OpenRouter Free-Tier Reliability

The OpenRouter free tier returns 429 (rate limited) frequently. The pipeline
retries per `llm_client.py` but cannot guarantee completion for demo conditions.
Use Anthropic for any presentation or evaluation that requires reliable output.

### Anthropic Model ID Versioning

The Anthropic API rejects undated model aliases (e.g., `claude-haiku` without a
date). All model IDs must be pinned with dates. Current defaults are pinned in
`dischargeiq/utils/llm_client.py`. If Anthropic retires a model, update the
default there and in any `.env` overrides.
