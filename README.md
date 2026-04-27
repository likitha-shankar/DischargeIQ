# DischargeIQ

Multi-agent system that reads hospital discharge PDFs and generates
plain-language patient education at a 6th-grade reading level.

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
dischargeiq/       Python package (agents, pipeline, models, prompts)
tests/             Root-level integration runners + tests/manual/ smoke scripts
streamlit_app.py   Dashboard frontend
start.sh / .bat    One-command startup scripts
requirements.txt   Pinned dependencies
.env.example       Env template — copy to .env and fill in keys
```

See the README inside each folder under `dischargeiq/` for details on
that module.

## License

See `LICENSE`.
