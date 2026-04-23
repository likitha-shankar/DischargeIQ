# `models/` — Pydantic schemas

Typed data contracts between agents, the orchestrator, and the API
layer. Every cross-module boundary uses a model from this folder.

## Files

- `extraction.py` — `ExtractionOutput` (Agent 1 response),
  `Medication`, `FollowUpAppointment`. **Locked schema** — do not
  rename fields without team sign-off. Downstream agents depend on it.
- `pipeline.py` — `PipelineResponse` (final response returned by
  `POST /analyze`, aggregating all agent outputs + FK scores +
  warnings + pipeline status).

## Using

```python
from dischargeiq.models.extraction import ExtractionOutput, Medication
from dischargeiq.models.pipeline   import PipelineResponse
```

## Rules

- All optional fields default to `None` for singletons or `[]` for
  lists — never `Optional[...]` without a default.
- Agent 1 may return `null` for any field; downstream agents must
  handle that, never guess.
