# Task 4.7 - Final Summary Report ◑

**Deliverable:** accuracy, comprehension lift, telemetry and limitations,
stated plainly.

**Artifact:** `docs/FINAL_SUMMARY_REPORT.md`, draft `3661a04` (16 Aug 2026).

**Status:** draft written; **stale on accuracy and blocked on comprehension.**

## What needs refreshing before it is final

The draft predates the completed corpus run. Current figures:

| Measure | Draft basis | Current |
|---|---|---|
| Corpus coverage | 55 documents | **106 of 106** |
| Readability | 99% of 220 | **98% of 424**, mean 4.08 |
| Numeric grounding | 47 of 55 flagged | **25 of 106** |
| Stratum breadth | one (dictated) | one, **plus a measured degraded stratum** |

## What it still cannot state

**Comprehension lift.** The 13% → 50-70% figure is a target with no
measurement behind it. It depends on task 2.6 recruiting, and the report must
not present the target as a result.

**Clinician verification.** Aggregates task 4.2, which is blocked.

## The limitations section is the point

Three that belong in it, all measured rather than assumed:

- Every clean-corpus figure generalises to **dictated documents only**.
- Under degradation, warning signs retain **85.5%** against 93.7% clean, and
  what is lost is the document-specific ones. `evaluation/fax_stratum_report.md`.
- Omission is measured only on the leg this system owns - content Agent 1
  captured that never reached the patient. The source-to-extraction half
  needs a clinician-annotated gold standard that does not exist.

A report that hides these cannot be trusted on the numbers it does state.
