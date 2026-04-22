# `dischargeiq/` — core package

FastAPI backend + multi-agent pipeline. All production code lives here.

## Files

- `main.py` — FastAPI app. Endpoints: `GET /health`, `POST /analyze`,
  `POST /chat`. Entry point for `uvicorn dischargeiq.main:app`.

## Subpackages

| Folder        | What it does                                                  |
|---------------|---------------------------------------------------------------|
| `agents/`     | LLM-powered agents (Agent 1 extraction, Agent 2 diagnosis)    |
| `pipeline/`   | Orchestrator that wires the agents into a single pipeline     |
| `models/`     | Pydantic schemas (`ExtractionOutput`, `PipelineResponse`)     |
| `prompts/`    | System prompts used by each agent and the LLM judge           |
| `utils/`      | Shared helpers (LLM client, FK scorer, logger, warnings)      |
| `db/`         | PostgreSQL schema + write helpers (not yet wired into main)   |
| `evaluation/` | FK readability log written to on every Agent 2 run            |
| `tests/`      | Integration/hallucination test suite and PDF fixtures         |

## Import paths

All modules import as `dischargeiq.<subpackage>.<module>`:

```python
from dischargeiq.pipeline.orchestrator import run_pipeline
from dischargeiq.models.pipeline import PipelineResponse
from dischargeiq.utils.scorer import fk_check
```
