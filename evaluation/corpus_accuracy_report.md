# Corpus accuracy run (task 3.4)

Generated 2026-08-16 by `scripts/corpus_accuracy_report.py`
over 68 pipeline outputs in `evaluation/corpus_outputs/`.

The corpus is 106 real de-identified discharge summaries (MTSamples
transcriptions with identifiers removed). Neither the corpus nor these
outputs is committed - both are rebuilt from scripts - so this report is
the durable artefact of the run.

## 1. Readability

Target: Flesch-Kincaid grade <= 6.0 on every patient-facing output.

| Agent | Section | Mean | Max | At or under target |
|---|---|---|---|---|
| agent2 | What happened | 3.74 | 6.29 | 61/63 |
| agent3 | Medications | 4.12 | 6.33 | 60/61 |
| agent4 | Recovery | 4.32 | 5.58 | 59/59 |
| agent5 | Warning signs | 4.53 | 5.89 | 56/56 |

**99% of 239 outputs meet the sixth-grade target**, mean grade 4.17.

## 2. Grounding (output against source)

Checked 68 of 68 outputs against their source document.

- **Medication names not present in the source: 0**. Agent 1 is contractually forbidden from inventing a field value, so any hit here is a contract violation.
- **Outputs containing a number absent from the source: 50**. Week numbers and 911 are excluded, so this measures dosages, weights and thresholds.

These are not random fabrications. They fall into two classes,
and only one of them is a defect in this system:

**Clinical thresholds the prompts supply** (51 occurrences): fever limits such as "over 101 F" and "100.4 F". These come from the agent prompts, not from the patient's document. They are standard clinical guidance, but they are shown to the patient as if their own paperwork said so.

**Activity targets the model invents** (40 occurrences): "walk for 15 minutes each day", "do not bend your new knee more than 90 degrees". The agent 4 prompt REQUIRES one specific goal per week, so when the source document sets none, the model supplies a number. The requirement causes the invention.

**Everything else**: 6 occurrences.

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
| follow-up appointments | 60/68 (88%) |
| medications | 59/68 (87%) |
| activity or diet | 27/68 (40%) |
| discharge date | 25/68 (37%) |
| red flag symptoms | 17/68 (25%) |

## 4. Pipeline status

| Status | Count |
|---|---|
| `complete_with_warnings` | 53 |
| `partial` | 14 |
| `complete` | 1 |

`complete_with_warnings` is the expected majority on real paperwork:
it means every agent ran and the source was missing sections.
`partial` means an agent failed and retrying may help.

