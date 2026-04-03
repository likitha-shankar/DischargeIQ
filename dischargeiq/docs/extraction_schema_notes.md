# Extraction Schema Notes

Locked schema for Agent 1 — do not change without team sign-off.

## Field definitions (one line each)

**patient_name:** Patient full name from the document header or demographics line, or null if absent.

**discharge_date:** Discharge date string as printed on the summary (often near the top), or null if absent.

**primary_diagnosis:** Main condition treated during the stay (principal or discharge diagnosis) — required when documented.

**secondary_diagnoses:** Additional documented diagnoses or comorbidities, or `[]` if none.

**procedures_performed:** Procedures or surgeries during the stay, or `[]` if none listed.

**medications:** Discharge med list as objects with `name` (required), and optional `dose`, `frequency`, `duration`, `status` (new/changed/continued/discontinued), or `[]` if none.

**follow_up_appointments:** Scheduled or recommended visits with optional `provider`, `specialty`, `date`, `reason`, or `[]` if none.

**activity_restrictions:** Activity limits at discharge, or `[]` if none.

**dietary_restrictions:** Diet orders at discharge, or `[]` if none.

**red_flag_symptoms:** Warning symptoms or return-to-ER instructions, or `[]` if none.

**discharge_condition:** Condition or disposition at discharge (e.g. stable), or null if absent.

**extraction_warnings:** Strings describing uncertain or failed extractions for downstream agents, or `[]` if none.

## Null rule

- Optional scalar fields: use `null` when missing or unreadable — never guess.
- List fields: use `[]` when empty, never `null`.
- Agent 1 must never fabricate clinical values; prefer null/`[]` over wrong data.
