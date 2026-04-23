# `pipeline/` — agent orchestrator

Wires the individual agents into a single end-to-end pipeline.
Everything downstream (FastAPI, CLI tests, Streamlit) calls into
`run_pipeline()` — nothing else talks to the agents directly.

## Files

- `orchestrator.py` — `run_pipeline(pdf_path) -> PipelineResponse`.
  Extracts PDF text, runs Agent 1, runs Agent 2, aggregates FK scores
  + warnings, and never raises. On any agent failure it sets
  `pipeline_status = "partial"` and fills in a safe fallback.

## Using

```python
from dischargeiq.pipeline.orchestrator import run_pipeline

result = run_pipeline("path/to/discharge.pdf")
print(result.pipeline_status)        # "complete" | "complete_with_warnings" | "partial"
print(result.extraction.primary_diagnosis)
print(result.diagnosis_explanation)
```

## Invariants

- `run_pipeline` always returns a `PipelineResponse`. It does not
  raise on bad PDFs, missing fields, or LLM errors.
- `pipeline_status` is:
  - `"complete"` when every agent succeeded with no extraction warnings.
  - `"complete_with_warnings"` when every agent succeeded but extraction
    completeness warnings were raised.
  - `"partial"` when one or more agents failed and fallback content was used.
- `fk_scores["agent2"]` is always present.
