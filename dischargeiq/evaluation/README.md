# `evaluation/` — readability telemetry

Append-only log of Flesch-Kincaid scores from agent runs. Used to
track reading-level drift over time across Agents 2–6.

## Files

- `fk_log.csv` — one row per agent invocation. Columns:
  `timestamp, document_id, fk_grade, passes, threshold`.
  Written by each agent's own `_log_fk_score()` function
  (in `diagnosis_agent.py`, `medication_agent.py`, `recovery_agent.py`,
  `escalation_agent.py`, `patient_simulator_agent.py`).
  Do not edit by hand.

## Inspecting

```bash
# Recent 20 runs
tail -20 dischargeiq/evaluation/fk_log.csv

# Pass rate at threshold 6.0
awk -F, 'NR>1{t++; if($4=="True") p++} END{print p"/"t}' \
    dischargeiq/evaluation/fk_log.csv
```

## Rotating

The file is append-only and grows forever. When it gets inconveniently
large, archive it:

```bash
mv dischargeiq/evaluation/fk_log.csv \
   dischargeiq/evaluation/fk_log.$(date +%Y%m%d).csv
```

A fresh log is created automatically on the next Agent 2 run.
