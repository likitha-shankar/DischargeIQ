# `dischargeiq/` — core package

FastAPI backend + multi-agent pipeline. All production code lives here.

## Files

- `main.py` — FastAPI app. Endpoints: `GET /health`, `POST /analyze`,
  `POST /chat`. Entry point for `uvicorn dischargeiq.main:app`.

## Subpackages

| Folder        | What it does                                                                          |
|---------------|---------------------------------------------------------------------------------------|
| `agents/`     | LLM-powered agents (Agents 1–6: extraction, diagnosis, medication, recovery, escalation, patient simulator) |
| `pipeline/`   | Orchestrator that wires all six agents into a single pipeline                         |
| `models/`     | Pydantic schemas (`ExtractionOutput`, `PipelineResponse`, `PatientSimulatorOutput`)   |
| `prompts/`    | System prompts used by each agent and the LLM judge                                   |
| `utils/`      | Shared helpers (LLM client, FK scorer, logger, warnings, extraction scope, HTML builder) |
| `db/`         | PostgreSQL schema + async write helpers (wired into orchestrator via `save_discharge_history`) |
| `evaluation/` | FK readability log — one row appended per agent run by each agent's `_log_fk_score`  |
| `tests/`      | Integration/hallucination test suite and PDF fixtures                                 |

## Import paths

All modules import as `dischargeiq.<subpackage>.<module>`:

```python
from dischargeiq.pipeline.orchestrator import run_pipeline
from dischargeiq.models.pipeline import PipelineResponse
from dischargeiq.utils.scorer import fk_check
```
