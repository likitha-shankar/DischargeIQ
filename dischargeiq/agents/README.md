# `agents/` — LLM-powered agents

Each agent is a pure function: it takes typed input, calls an LLM with
a dedicated system prompt, validates the response, and returns typed
output. The orchestrator composes all six.

## Files

- `extraction_agent.py` — **Agent 1**. Reads raw PDF text, returns a
  validated `ExtractionOutput` (structured fields: diagnosis,
  medications, follow-ups, red flags, etc.). Uses the provider
  configured by `LLM_PROVIDER`.
- `diagnosis_agent.py` — **Agent 2**. Takes `ExtractionOutput`, writes
  a plain-language diagnosis explanation at FK grade ≤ 6. Retries once
  if FK > 6.5 and keeps the lower-scoring attempt. Logs FK score to
  `evaluation/fk_log.csv`.
- `medication_agent.py` — **Agent 3**. Takes `ExtractionOutput.medications`
  and `primary_diagnosis`, produces a per-drug plain-language explanation
  (why prescribed, what it does, side effects, when to call the doctor).
  FK target ≤ 6.0; logs to `evaluation/fk_log.csv`.
- `recovery_agent.py` — **Agent 4**. Takes `ExtractionOutput`, produces a
  week-by-week recovery guide covering expected feelings, activity level,
  normal vs alarming symptoms, and weekly goals. FK target ≤ 6.0.
- `escalation_agent.py` — **Agent 5** (safety-critical). Produces a
  three-tier decision tree: call 911, go to ER today, call doctor during
  office hours. Tier headers are fixed strings parsed by `streamlit_app.py`
  — do not change them without updating the UI renderer. FK target ≤ 6.0.
- `patient_simulator_agent.py` — **Agent 6**. Simulates a confused patient
  reading the document, identifies gaps between what is written and what a
  lay reader still needs to know. Returns `PatientSimulatorOutput` with
  `missed_concepts`, `overall_gap_score` (0–10), and a short summary.
  FK threshold ≤ 8.0; logs to `evaluation/fk_log.csv`.

## Calling an agent directly

```python
from dischargeiq.agents.extraction_agent       import run_extraction_agent
from dischargeiq.agents.diagnosis_agent        import run_diagnosis_agent
from dischargeiq.agents.medication_agent       import run_medication_agent
from dischargeiq.agents.recovery_agent         import run_recovery_agent
from dischargeiq.agents.escalation_agent       import run_escalation_agent
from dischargeiq.agents.patient_simulator_agent import run_patient_simulator_agent

extraction  = run_extraction_agent(pdf_text, document_id="smoke-test")
explanation = run_diagnosis_agent(extraction, document_id="smoke-test")
meds        = run_medication_agent(extraction, document_id="smoke-test")
recovery    = run_recovery_agent(extraction, document_id="smoke-test")
escalation  = run_escalation_agent(extraction, document_id="smoke-test")
simulator   = run_patient_simulator_agent(extraction, document_id="smoke-test")
```

## Rules every agent follows

1. Never fabricate a value. `null` beats a wrong answer.
2. Never instruct a patient to stop or change a medication.
3. Every text output is passed through `utils.scorer.fk_check`.
4. Every external call is wrapped in `try/except` — no silent swallows.

## Adding a new agent

1. Add the system prompt to `dischargeiq/prompts/`.
2. Add the response schema to `dischargeiq/models/` if needed.
3. Add `run_<name>_agent()` here — same pattern as the existing agents.
4. Wire it into `dischargeiq/pipeline/orchestrator.py`.
