# Extraction Schema Notes

- `primary_diagnosis` is the only required string field.
- All list fields default to `[]`, never `null`.
- `medication.status` should be one of: `new`, `changed`, `continued`, `discontinued`, or `null`.
- Agent 1 must never fabricate values. If unsure, return `null`.
- This schema is **LOCKED** — do not modify without full team sign-off.
