# Task 3.4 - Full-Corpus Automated Accuracy Run ✅

**Deliverable:** output-to-source diffing, readability logging and chat
grounding across the corpus, with results.

**Report:** `evaluation/corpus_accuracy_report.md` (31 Aug 2026, 106 of 106
documents). Per-stratum extension: `evaluation/fax_stratum_report.md`.

**Runner:** `scripts/run_corpus_for_review.py` (resumable; `--stale`
regenerates only outputs whose prompt stamp differs from the prompts on
disk). Analysis: `scripts/corpus_accuracy_report.py`.

## Coverage history, because the number moved

| Date | Documents | Note |
|---|---|---|
| 16 Aug | 55 of 106 (52%) | Did not meet acceptance under any reading |
| 31 Aug | **106 of 106** | Complete |

The tooling was never the gap. Throughput was: `gemini-2.5-flash-lite` on
Vertex runs on **dynamic shared quota** with no per-project limit, so the
429s throttling the run could not be paced away and no quota increase could
be requested. The nightly catch-up cron also never ran - macOS TCC blocks
`/usr/sbin/cron` on a `~/Desktop` path - so the remaining documents were
worked through in supervised batches.

## Results

| Measure | Result |
|---|---|
| Readability, FK ≤ 6.0 | 416 / 424 (98%), mean grade 4.08 |
| Medication names absent from source | **0 / 106** |
| Medication recall (extracted → patient) | 529 / 532 (99.4%) |
| Warning-sign recall | 89 / 95 (93.7%) |
| Outputs with a number absent from source | 25 / 106 |
| Pipeline completed | 106 / 106 (104 `complete_with_warnings`, 2 `complete`) |

Omission is reported separately from fabrication on purpose (Liebovitz item
2.5). A summary that drops a warning sign looks exactly like one that does
not, so a readability score cannot see it and a combined figure would hide
it behind the fabrication number.

## The numeric-grounding finding

Of the 25 flagged outputs, 22 carry clinical thresholds the **prompt itself**
supplied ("over 101 F") and 3 carry activity targets the model invented
because the Agent 4 prompt required a weekly goal when the source set none.
Both classes were fixed on 25 Aug: on a 10-document verification set,
documents carrying an invented value went from **8/10 to 0/10**.

Whether a general fever threshold may be shown to a patient as if their own
paperwork said so is a clinical call, not a prompt-file call. It remains the
first item for task 4.2 review.

## What this run cannot tell you

The clean corpus is a single stratum - all 106 are dictated transcriptions -
so every figure above generalises to dictated documents only. That gap is
closed separately in `evaluation/fax_stratum_report.md`, which found warning
signs retaining 85.5% under degradation against 93.7% here, and medications
94.9% against 99.4%.

There is also no clinician-annotated gold standard, so the source-to-extraction
half of omission is unmeasured. These figures cover only the leg this system
owns completely: content Agent 1 captured that never reached the patient.
