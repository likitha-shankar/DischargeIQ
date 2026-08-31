# Corpus accuracy run (task 3.4)

Generated 2026-08-31 by `scripts/corpus_accuracy_report.py`
over 106 pipeline outputs in `evaluation/corpus_outputs/`.

The corpus is 106 real de-identified discharge summaries (MTSamples
transcriptions with identifiers removed). Neither the corpus nor these
outputs is committed - both are rebuilt from scripts - so this report is
the durable artefact of the run.

## 0. What produced these numbers

An accuracy figure means nothing without the model that produced it.
Provider defaults are floating aliases, so the same setting can resolve
to a different model over time and silently invalidate every number
below while this file still looks current.

| Provider | Model | Outputs |
|---|---|---|
| vertex | `<provider default>` | 106 |

## 1. Readability

Target: Flesch-Kincaid grade <= 6.0 on every patient-facing output.

| Agent | Section | Mean | Max | At or under target |
|---|---|---|---|---|
| agent2 | What happened | 3.26 | 6.40 | 104/106 |
| agent3 | Medications | 4.04 | 6.40 | 105/106 |
| agent4 | Recovery | 4.47 | 8.76 | 102/106 |
| agent5 | Warning signs | 4.54 | 6.33 | 104/106 |

**98% of 424 outputs meet the sixth-grade target**, mean grade 4.08.

## 2. Grounding (output against source)

Checked 106 of 106 outputs against their source document.

- **Medication names not present in the source: 0**. Agent 1 is contractually forbidden from inventing a field value, so any hit here is a contract violation.
- **Outputs containing a number absent from the source: 25**. Week numbers and 911 are excluded, so this measures dosages, weights and thresholds.

These are not random fabrications. They fall into two classes,
and only one of them is a defect in this system:

**Clinical thresholds the prompts supply** (22 occurrences): fever limits such as "over 101 F" and "100.4 F". These come from the agent prompts, not from the patient's document. They are standard clinical guidance, but they are shown to the patient as if their own paperwork said so.

**Activity targets the model invents** (3 occurrences): "walk for 15 minutes each day", "do not bend your new knee more than 90 degrees". The agent 4 prompt REQUIRES one specific goal per week, so when the source document sets none, the model supplies a number. The requirement causes the invention.

**Everything else**: 8 occurrences.

### The question for clinician review

Both classes are defensible as general patient education and
indefensible as instructions attributed to a specific discharge
document. A knee protocol differs between surgeons; a fever
threshold differs for an immunocompromised patient. This is the
first thing to put in front of the LOF reviewers (task 4.2), and
it is not a decision to make unilaterally in a prompt file.

## 3. Omission (extraction against patient-facing output)

Errors of omission are the dominant failure mode and are invisible to
the patient: a dropped medication yields a clean, confident, incorrect
document. Fluency cannot detect this, which is why it is reported
separately from readability.

**Scope.** This measures only the leg this system owns completely:
content Agent 1 successfully extracted that never reached the patient.
The extraction record is the ground truth, so no annotation is needed.
The source-to-extraction leg is the other half of omission risk and
needs the clinician-annotated gold standard. **Do not read these as
total omission rates.**

| Content | Extracted | Reached the patient | Recall |
|---|---|---|---|
| Medications (agent 3) | 532 | 529 | 99.4% |
| Warning signs (agent 5) | 95 | 89 | 93.7% |

Warning signs are counted separately because Agent 5 is the
safety-critical output: a red flag the document listed and the guide
dropped is the highest-consequence omission in the system.

Dropped medications:

- `mtsamples_005`: Medications
- `mtsamples_056`: Other Current Home Medications
- `mtsamples_081`: Pre-Admission Medications

Dropped warning signs:

- `mtsamples_034`: hemoptysis
- `mtsamples_035`: other problems
- `mtsamples_056`: increasing shortness of breath
- `mtsamples_062`: increased temperature greater than 101.5; increased pain that is not relieved by current pain regimen
- `mtsamples_075`: redness, drainage, or warmth around his incision site

## 4. What the source documents actually contain

The reason an absent section is treated as a property of the
paperwork rather than a failure of this system.

| Field | Documents containing it |
|---|---|
| medications | 94/106 (89%) |
| follow-up appointments | 93/106 (88%) |
| activity or diet | 41/106 (39%) |
| discharge date | 30/106 (28%) |
| red flag symptoms | 28/106 (26%) |

## 5. Pipeline status

| Status | Count |
|---|---|
| `complete_with_warnings` | 104 |
| `complete` | 2 |

`complete_with_warnings` is the expected majority on real paperwork:
it means every agent ran and the source was missing sections.
`partial` means an agent failed and retrying may help.

