# Corpus accuracy run (task 3.4)

Generated 2026-08-25 by `scripts/corpus_accuracy_report.py`
over 59 pipeline outputs in `evaluation/corpus_outputs/`.

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
| unrecorded | `unrecorded` | 59 |

**`unrecorded` means the output predates provenance stamping (added 25 Aug 2026).** Those numbers cannot be tied to a model version. Re-run those documents before citing this report as gate evidence.

## 1. Readability

Target: Flesch-Kincaid grade <= 6.0 on every patient-facing output.

| Agent | Section | Mean | Max | At or under target |
|---|---|---|---|---|
| agent2 | What happened | 3.73 | 6.29 | 57/59 |
| agent3 | Medications | 4.11 | 6.33 | 58/59 |
| agent4 | Recovery | 4.31 | 5.58 | 59/59 |
| agent5 | Warning signs | 4.51 | 5.89 | 59/59 |

**99% of 236 outputs meet the sixth-grade target**, mean grade 4.17.

## 2. Grounding (output against source)

Checked 59 of 59 outputs against their source document.

- **Medication names not present in the source: 0**. Agent 1 is contractually forbidden from inventing a field value, so any hit here is a contract violation.
- **Outputs containing a number absent from the source: 50**. Week numbers and 911 are excluded, so this measures dosages, weights and thresholds.

These are not random fabrications. They fall into two classes,
and only one of them is a defect in this system:

**Clinical thresholds the prompts supply** (49 occurrences): fever limits such as "over 101 F" and "100.4 F". These come from the agent prompts, not from the patient's document. They are standard clinical guidance, but they are shown to the patient as if their own paperwork said so.

**Activity targets the model invents** (39 occurrences): "walk for 15 minutes each day", "do not bend your new knee more than 90 degrees". The agent 4 prompt REQUIRES one specific goal per week, so when the source document sets none, the model supplies a number. The requirement causes the invention.

**Everything else**: 6 occurrences.

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
| Medications (agent 3) | 307 | 307 | 100.0% |
| Warning signs (agent 5) | 53 | 53 | 100.0% |

Warning signs are counted separately because Agent 5 is the
safety-critical output: a red flag the document listed and the guide
dropped is the highest-consequence omission in the system.

No omissions detected on this run.

## 4. What the source documents actually contain

The reason an absent section is treated as a property of the
paperwork rather than a failure of this system.

| Field | Documents containing it |
|---|---|
| follow-up appointments | 55/59 (93%) |
| medications | 51/59 (86%) |
| discharge date | 24/59 (41%) |
| activity or diet | 21/59 (36%) |
| red flag symptoms | 16/59 (27%) |

## 5. Pipeline status

| Status | Count |
|---|---|
| `complete_with_warnings` | 58 |
| `complete` | 1 |

`complete_with_warnings` is the expected majority on real paperwork:
it means every agent ran and the source was missing sections.
`partial` means an agent failed and retrying may help.

