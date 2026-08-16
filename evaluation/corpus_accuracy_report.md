# Corpus accuracy run (task 3.4)

Generated 2026-08-16 by `scripts/corpus_accuracy_report.py`
over 55 pipeline outputs in `evaluation/corpus_outputs/`.

The corpus is 106 real de-identified discharge summaries (MTSamples
transcriptions with identifiers removed). Neither the corpus nor these
outputs is committed - both are rebuilt from scripts - so this report is
the durable artefact of the run.

## 1. Readability

Target: Flesch-Kincaid grade <= 6.0 on every patient-facing output.

| Agent | Section | Mean | Max | At or under target |
|---|---|---|---|---|
| agent2 | What happened | 3.79 | 6.29 | 53/55 |
| agent3 | Medications | 4.14 | 6.33 | 54/55 |
| agent4 | Recovery | 4.30 | 5.58 | 55/55 |
| agent5 | Warning signs | 4.54 | 5.89 | 55/55 |

**99% of 220 outputs meet the sixth-grade target**, mean grade 4.19.

## 2. Grounding (output against source)

Checked 55 of 55 outputs against their source document.

- **Medication names not present in the source: 0**. Agent 1 is contractually forbidden from inventing a field value, so any hit here is a contract violation.
- **Outputs containing a number absent from the source: 47**. Week numbers and 911 are excluded, so this measures dosages, weights and thresholds.

These are not random fabrications. They fall into two classes,
and only one of them is a defect in this system:

**Clinical thresholds the prompts supply** (46 occurrences): fever limits such as "over 101 F" and "100.4 F". These come from the agent prompts, not from the patient's document. They are standard clinical guidance, but they are shown to the patient as if their own paperwork said so.

**Activity targets the model invents** (38 occurrences): "walk for 15 minutes each day", "do not bend your new knee more than 90 degrees". The agent 4 prompt REQUIRES one specific goal per week, so when the source document sets none, the model supplies a number. The requirement causes the invention.

**Everything else**: 5 occurrences.

### The question for clinician review

Both classes are defensible as general patient education and
indefensible as instructions attributed to a specific discharge
document. A knee protocol differs between surgeons; a fever
threshold differs for an immunocompromised patient. This is the
first thing to put in front of the LOF reviewers (task 4.2), and
it is not a decision to make unilaterally in a prompt file.

## 3. What the source documents actually contain

The reason an absent section is treated as a property of the
paperwork rather than a failure of this system.

| Field | Documents containing it |
|---|---|
| follow-up appointments | 51/55 (93%) |
| medications | 47/55 (85%) |
| discharge date | 23/55 (42%) |
| activity or diet | 19/55 (35%) |
| red flag symptoms | 15/55 (27%) |

## 4. Pipeline status

| Status | Count |
|---|---|
| `complete_with_warnings` | 54 |
| `complete` | 1 |

`complete_with_warnings` is the expected majority on real paperwork:
it means every agent ran and the source was missing sections.
`partial` means an agent failed and retrying may help.

