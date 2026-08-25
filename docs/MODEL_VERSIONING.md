# Model versioning and the re-evaluation trigger

Answers item 3.7 of the Dr. Liebovitz faculty review: *"pinned model versions
with a documented re-evaluation trigger on version change."*

The claim this project makes is measured accuracy. A measurement is only valid
for the model that produced it, so a model change is not a configuration
detail - it expires the evidence.

## The problem, stated plainly

`dischargeiq/utils/llm_client.py` resolves the Vertex model to
`google/gemini-2.5-flash-lite` when `LLM_MODEL` is unset, which is how
production runs. That string is a **floating alias**: Google decides what it
points to and can change it without notice. Nothing in this repository would
notice. The accuracy report would keep showing 99% readability and 307/307
medication recall while describing the behaviour of a model that is no longer
running.

`.env` leaves `LLM_MODEL` commented out deliberately, so that local runs match
Cloud Run. That is the right call for reproducing production behaviour and the
wrong one for reproducing an *evidence run*, and those two goals genuinely
conflict.

## What is now in place

**Provenance stamping (25 Aug 2026).** `scripts/run_corpus_for_review.py`
records `llm_provider` and `llm_model` into each output's `_review_meta`, and
`scripts/corpus_accuracy_report.py` reports them in section 0 of the accuracy
report. The report also refuses to look clean when it cannot vouch for itself:

- outputs written before this date show as `unrecorded`, with a warning that
  they cannot be tied to a model version
- if more than one configuration appears across the run, the report says the
  figures are not a single measurement

As of 25 Aug 2026 all 59 existing outputs are `unrecorded`. **They must be
re-run before the accuracy report is cited as gate evidence.**

## The re-evaluation trigger

Re-run the full corpus accuracy suite and regenerate the report when **any** of
the following changes:

1. `LLM_PROVIDER` changes, including a switch to the fallback provider for a
   sustained period.
2. `LLM_MODEL` changes, or the provider announces a change to what an alias
   resolves to.
3. Any agent system prompt in `dischargeiq/prompts/` changes. A prompt edit
   changes outputs as surely as a model swap; the 47/55 numeric-grounding
   finding traces to a prompt requirement, not to the model.
4. The extraction schema in `dischargeiq/models/extraction.py` changes, since
   it is the contract every downstream agent reads.

**Before quoting any accuracy figure externally**, check that section 0 of the
report names a single, recorded configuration. If it says `unrecorded`, or
lists more than one row, the number is not citable.

## Recommendation not yet acted on

Pin `LLM_MODEL` explicitly for evaluation runs, so evidence is reproducible,
while leaving production on the provider default so it tracks upstream fixes.
That means accepting a deliberate divergence between the evaluation
environment and production, which is a real trade-off and the opposite of the
16 Aug decision to keep `.env` matching Cloud Run. It is recorded here as a
decision to make rather than made unilaterally, because that earlier decision
was taken for a good reason: a Vertex-only model-name bug survived precisely
because local and production diverged.
