# Task 4.2 - Clinician Sample Verification ◻ BLOCKED

**Deliverable:** 1-2 LOF reviewers scoring 5-10 documents through the review
portal.

**Status:** the portal is built (`a5f5f43`, `ui/clinician_review.py`) and the
frozen output set exists. **Blocked on clinician availability.**

## The rubric was corrected before it was used

Rewritten 31 Jul 2026 to judge **fidelity to source** rather than general
clinical quality. A reviewer asked "is this good medical advice?" will grade
the model's medical knowledge. The question that matters is "does this say
what the patient's document said?", which is the only thing this system is
responsible for.

## The first thing to put in front of a reviewer

From the corpus accuracy run: **22 outputs carry clinical thresholds the
prompt supplied** - fever limits like "over 101 F" - shown to the patient as
though their own paperwork said so.

Both defensible as general patient education and indefensible as instructions
attributed to a specific document. A knee protocol differs between surgeons;
a fever threshold differs for an immunocompromised patient. This is not a
prompt-file decision and should not be made unilaterally.

## The second thing

From the fax stratum (25 pairs): under degradation, warning signs retain 85.5% against
93.7% clean, and the losses are the DOCUMENT-SPECIFIC ones - hemoptysis in
`mtsamples_034`, where the generic tiers survived and the patient's own
warning did not. The mitigation shipped (a notice on the escalation guide,
`2d66b80`) but whether it is sufficient is a clinical judgement.

## Blocks

Task 4.3 (fix pass tracing each flagged item to its closing commit) and part
of task 4.7 (the final summary aggregates this).

Same bottleneck as Liebovitz 3.5, the annotated gold standard. One clinician
session would unblock both.
