# `pipeline/` — agent orchestrator

Wires all six agents into a single end-to-end pipeline. Everything
downstream (FastAPI, CLI tests, Streamlit) calls into `run_pipeline()`
— nothing else talks to the agents directly.

## Files

- `orchestrator.py` — `run_pipeline(pdf_path, session_id=None, on_progress=None) -> PipelineResponse`.
  Extracts PDF text, runs Agent 1 (extraction), then Agents 2–5
  (diagnosis, medication, recovery, escalation) in sequence, then
  Agent 6 (patient simulator). Aggregates FK scores, extraction
  warnings, and DB persistence. Never raises — on any agent failure it
  sets `pipeline_status = "partial"` and fills in a safe fallback.

## Using

```python
from dischargeiq.pipeline.orchestrator import run_pipeline

result = run_pipeline("path/to/discharge.pdf")
print(result.pipeline_status)        # "complete" | "complete_with_warnings" | "partial"
print(result.extraction.primary_diagnosis)
print(result.diagnosis_explanation)
print(result.patient_simulator.overall_gap_score)
```

## Invariants

- `run_pipeline` always returns a `PipelineResponse`. It does not
  raise on bad PDFs, missing fields, or LLM errors.
- `pipeline_status` is:
  - `"complete"` when every agent succeeded with no extraction warnings.
  - `"complete_with_warnings"` when every agent succeeded but extraction
    completeness warnings were raised.
  - `"partial"` when one or more agents failed and fallback content was used.
- `fk_scores` contains keys for each agent that ran (`agent2`, `agent3`,
  `agent4`, `agent5`). `fk_scores["agent2"]` is always present.
- `patient_simulator` is `None` only if Agent 6 was explicitly skipped
  or failed; the pipeline does not crash in that case.
