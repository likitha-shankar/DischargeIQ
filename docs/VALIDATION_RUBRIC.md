# Discharge instruction validation rubric

**For:** Frank, who asked for input on rubric definition to support AI
accuracy measurement and liability management.

**Status:** built and running. This is not a proposal in the abstract - the
instrument exists as a role-gated review portal (`ui/clinician_review.py`),
the corpus is frozen, and the gate math is unit-tested. What follows is what
it currently does and the four decisions still genuinely open. React to those
and we adjust before scoring starts.

---

## The one page

Two clinicians independently score 50 frozen pipeline outputs. One 0-5 score
per document for **fidelity to the source**, plus a separate zero-tolerance
flag for invented clinical content. Comments required below 4 or on any flag.

**Gate:** full coverage, median ≥ 4.0, zero hallucination flags. Anything less
is a fail with a named fix list, not a soft pass.

---

## 1. What is being measured

**Fidelity to the source document. Not quality against an ideal summary.**

This distinction is the whole rubric. Real discharge paperwork is thin - in
our 106-document de-identified corpus:

| Field | Present in |
|---|---|
| Follow-up appointment | 69% |
| Discharge medications | 62% |
| Activity / diet restrictions | 53% |
| Warning signs | **34%** |

If reviewers score against an ideal summary, they measure US discharge
documentation, not our system, and every score is dominated by gaps we did not
create and cannot fix. So the instruction is: **judge only what the source
contained.**

Consequence, stated plainly: content missing from both source and output is
not penalized. Content present in the output but not the source is the
serious failure and gets flagged separately from the score.

---

## 2. The 0-5 scale, with anchors

Anchor sentences matter more than the numbers - without them, two reviewers
mean different things by "3".

| Score | Anchor |
|---|---|
| **5** | I would hand this to my own patient unchanged. |
| **4** | Accurate and safe. Minor wording I would tweak, nothing I would correct. |
| **3** | Accurate but weakened - oversimplified, or something important is buried. |
| **2** | Something is misleading. Technically defensible, wrong impression. |
| **1** | Contains a clinical error, or omits something the source made central. |
| **0** | Unusable, or unsafe to give a patient. |

**Comments required below 4**, because the fix pass works from them. A score
of 3 with no comment is an unusable data point.

---

## 3. The hallucination flag - separate and absolute

A checkbox, not part of the score: **any medication, dose, or diagnosis in the
output that is not in the source document.**

Kept separate on purpose. A single invented medication is not "one point off"
- it is a different category of failure, the one that ends a health system
conversation. One flag anywhere fails the gate regardless of the median.

Rationale for liability: this gives a defensible, countable claim - *"two
independent clinicians reviewed 50 documents and flagged zero instances of
invented clinical content"* - rather than an accuracy percentage that invites
a question we cannot answer.

---

## 4. Gate arithmetic

- **Median, not mean.** One catastrophic document should not be averaged away
  by good ones, and one perfect document should not rescue a weak set.
- **Median of per-document medians**, so a double-scored document does not
  weigh twice.
- **Coverage required.** The gate reads FAIL until every document is scored,
  so a partial run cannot be presented as a pass.
- **Below-4.0 documents become an explicit fix worklist**, which is the
  deliverable of the pass after this one.

---

## 5. Method decisions already taken

| Decision | Choice | Why |
|---|---|---|
| Reviewers | 2, independent | Disagreement is signal; one reviewer is an opinion |
| Blinding | Reviewers see the source beside the output | Fidelity is unjudgeable without it |
| Sample | 50 documents, frozen before scoring | A live-regenerated set is not evidence |
| Effort | 10-15 min/document, self-paced | ~2 hours per reviewer total |
| Storage | Structured scores only, in Neon | Agent free-text stays on disk, per repo rule |

---

## 6. The four decisions still open - this is the ask

1. **Is median ≥ 4.0 the right bar** for a patient-facing tool? It is
   currently our number, not a clinical one.

2. **Is "judge only what the source contained" correct?** The alternative -
   penalizing gaps the hospital left - produces lower scores and a different,
   arguably more honest, claim. We think it measures the wrong thing, but this
   is the call most worth overriding us on.

3. **Is "invented content" the right words for the flag?** Reviewers have to
   recognize the thing instantly. "Hallucination" is our vocabulary, not
   theirs. "Not in the source" may be clearer than either.

4. **Is a discharge nurse or coordinator the right reviewer**, rather than a
   physician? Everything about sample size and timeline follows from this.

---

## 7. What this rubric deliberately does not measure

Worth stating so no one reads more into the result than it supports:

- **Not clinical outcomes.** No claim about readmission, adherence, or harm.
- **Not comprehension.** That is the teach-back quiz, measured separately as a
  before/after delta.
- **Not the chatbot.** Only the six agent outputs are scored. Grounded chat
  needs its own instrument.
- **Not generalization.** 50 documents across five diagnosis families. It
  supports "reviewed and found faithful on this corpus", nothing wider.

---

## 8. Runbook

1. `python scripts/run_corpus_for_review.py` - freezes outputs (~30s/doc,
   resumable).
2. Set `CLINICIAN_ACCESS_CODE` in `.env`; share with reviewers.
3. `streamlit run ui/clinician_review.py --server.port 8503`.
4. Watch the gate sidebar; export the below-4.0 worklist when scoring closes.

Gate math is in `ui/review_analytics.py`, unit-tested in
`dischargeiq/tests/test_review_analytics.py` (rollup medians, hallucination
taint, coverage requirement, worklist).
