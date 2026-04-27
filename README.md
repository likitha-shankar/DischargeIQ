# DischargeIQ

DischargeIQ is a **patient-friendly chatbot** grounded in your discharge
document, plus an **AI simulation layer** that surfaces missed concepts —
questions a confused patient would ask that the document does not answer.

Upload your discharge PDF: get plain-language answers to your questions via
the chat panel, and see what gaps the AI found before you go home. Six
specialised agents run in sequence: Agent 1 extracts structured data; Agents
2–5 produce four patient-facing education sections; Agent 6 (AI patient
simulator) identifies missed concepts and scores document gaps 0–10.

## Requirements

- Python 3.11+
- API credentials for your chosen **`LLM_PROVIDER`** (see `.env.example`).
  **All agents** use the same provider: `anthropic` (default, Haiku), `openrouter`,
  `openai`, or `ollama`. For higher-quality Claude runs / evals, set
  **`LLM_MODEL=claude-sonnet-4-20250514`** (undated model ids can 404).

## Quick start

```bash
git clone <repo-url>
cd DischargeIQ
./start.sh            # macOS / Linux
start.bat             # Windows
```

First run creates `.venv`, installs `requirements.txt`, copies
`.env.example` → `.env`, and exits telling you which keys to fill in.
Second run launches both servers.

## Configure `.env`

Open `.env` and set:

- `LLM_PROVIDER` — `anthropic` (default, Haiku), `openrouter`, `openai`, or `ollama`
- The matching key: `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, or
  `ANTHROPIC_API_KEY` (Ollama needs no key)
- Optional: `LLM_MODEL` — required to pin Sonnet for `anthropic` (see `.env.example`)

## Running

- **Both servers (recommended):** `./start.sh` or `start.bat`
- **Backend only:** `uvicorn dischargeiq.main:app --reload`
- **Frontend only:** `streamlit run streamlit_app.py`

Open the dashboard at http://127.0.0.1:8501.

## Testing

```bash
# Fast pytest suite (API guardrails, resilience mocks — seconds)
.venv/bin/python -m pytest dischargeiq/tests/

# Quiet dots only (harder to see progress — not recommended while debugging)
.venv/bin/python -m pytest dischargeiq/tests/ -q

# Full PDF corpus smoke (slow: real LLM + Neon — can take hours)
.venv/bin/python -m pytest -m slow dischargeiq/tests/test_all_corpus_smoke.py -v -s

# 8-case hallucination + integration suite (gates: 0 hallucinations) — separate script
python dischargeiq/tests/test_integration_hallucination.py

# 6-case real-world-format stress suite
python scripts/stress/run_stress_fixtures.py                  # all 6
python scripts/stress/run_stress_fixtures.py --fixtures 9,14  # subset

# Root integration runners (LLM / real PDFs — manual)
python tests/test_agent1.py
python tests/test_agents_1_2.py

# API / DB smoke scripts (manual)
python tests/manual/test_claude_api.py
python tests/manual/test_neon_db.py
```

Default `pytest` settings live in `pytest.ini` (**verbose**, **skip `slow`**; default discovery is `dischargeiq/tests/` only).

## Repo layout

```
dischargeiq/
├── agents/            Agents 1–6 (extraction → education → simulator)
├── pipeline/          Async orchestrator wiring all agents
├── models/            Pydantic models (ExtractionOutput, PipelineResponse)
├── prompts/           System prompts for all 6 agents + LLM judge
├── utils/             FK scorer, LLM client, warnings, logger
├── db/                Neon history persistence
├── tests/             Pytest suites (guardrails, hallucination, corpus)
├── evaluation/        FK logs, cost estimates, judge results
└── docs/              Extraction schema reference
tests/             Root-level integration runners + tests/manual/ smoke scripts
streamlit_app.py   6-tab Streamlit dashboard (What Happened / Medications /
                   Appointments / Warning Signs / Recovery / AI Review)
start.sh / .bat    One-command startup scripts
requirements.txt   Pinned dependencies
.env.example       Env template — copy to .env and fill in keys
```

See the README inside each folder under `dischargeiq/` for details on
that module.

## License

See `LICENSE`.
