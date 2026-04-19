# DischargeIQ

Multi-agent system that reads hospital discharge PDFs and generates
plain-language patient education at a 6th-grade reading level.

## Requirements

- Python 3.11+
- An Anthropic API key (Claude Sonnet powers Agents 2–5)
- One of: OpenRouter key, OpenAI key, or local Ollama
  (Agent 1 extraction provider — configured via `LLM_PROVIDER`)

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

- `ANTHROPIC_API_KEY` — required (Agents 2–5)
- `LLM_PROVIDER` — one of `openrouter` (default), `openai`,
  `anthropic`, or `ollama`
- The matching provider key:
  `OPENROUTER_API_KEY` / `OPENAI_API_KEY` (not needed for `ollama`)

## Running

- **Both servers (recommended):** `./start.sh` or `start.bat`
- **Backend only:** `uvicorn dischargeiq.main:app --reload`
- **Frontend only:** `streamlit run streamlit_app.py`

Open the dashboard at http://127.0.0.1:8501.

## Testing

```bash
# 8-case hallucination + integration suite (gates: 0 hallucinations)
python dischargeiq/tests/test_integration_hallucination.py

# 6-case real-world-format stress suite
python run_stress_fixtures.py                 # all 6
python run_stress_fixtures.py --fixtures 9,14 # subset
```

## Repo layout

```
dischargeiq/       Python package (agents, pipeline, models, prompts)
streamlit_app.py   Dashboard frontend
start.sh / .bat    One-command startup scripts
requirements.txt   Pinned dependencies
.env.example       Env template — copy to .env and fill in keys
```

See the README inside each folder under `dischargeiq/` for details on
that module.

## License

See `LICENSE`.
