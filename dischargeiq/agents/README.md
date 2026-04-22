# `agents/` — LLM-powered agents

Each agent is a pure function: it takes typed input, calls an LLM with
a dedicated system prompt, validates the response, and returns typed
output. The orchestrator composes them.

## Files

- `extraction_agent.py` — **Agent 1**. Reads raw PDF text, returns a
  validated `ExtractionOutput` (structured fields: diagnosis,
  medications, follow-ups, red flags, etc.). Uses the provider
  configured by `LLM_PROVIDER`.
- `diagnosis_agent.py` — **Agent 2**. Takes `ExtractionOutput`, writes
  a plain-language diagnosis explanation at FK grade ≤ 6. Retries once
  if FK > 6.5 and keeps the lower-scoring attempt.

## Calling an agent directly

```python
from dischargeiq.agents.extraction_agent import run_extraction_agent
from dischargeiq.agents.diagnosis_agent  import run_diagnosis_agent

extraction  = run_extraction_agent(pdf_text, document_id="smoke-test")
explanation = run_diagnosis_agent(extraction, document_id="smoke-test")
```

## Rules every agent follows

1. Never fabricate a value. `null` beats a wrong answer.
2. Never instruct a patient to stop or change a medication.
3. Every text output is passed through `utils.scorer.fk_check`.
4. Every external call is wrapped in `try/except` — no silent swallows.

## Adding a new agent

1. Add the system prompt to `dischargeiq/prompts/`.
2. Add the response schema to `dischargeiq/models/`.
3. Add `run_<name>_agent()` here — same shape as the existing two.
4. Wire it into `dischargeiq/pipeline/orchestrator.py`.
