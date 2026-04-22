# `evaluation/` — readability telemetry

Append-only log of Flesch-Kincaid scores from every Agent 2 run. Used
to track reading-level drift over time.

## Files

- `fk_log.csv` — one row per Agent 2 invocation. Columns:
  `timestamp, document_id, fk_grade, passes, threshold`.
  Written by `utils.scorer._log_fk_score()`. Do not edit by hand.

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
