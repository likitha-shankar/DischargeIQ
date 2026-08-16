# DischargeIQ - Final Summary Report

**Task 4.7.** Accuracy, comprehension lift, telemetry and limitations, stated
plainly.

**Status: DRAFT, 16 Aug 2026.** Two sections cannot be completed yet and are
marked so rather than estimated: clinician verification (task 4.2) needs LOF
reviewers, and real comprehension deltas (task 2.6) need the tester cohort.
Everything else is measured and reproducible from the repository.

Prepared by Likitha Shankar, sole developer.

---

## 1. What the system does

A patient uploads or photographs the discharge document they were handed on
the way out of hospital. Six agents read it and produce a plain-language
breakdown across seven sections: what happened, medications, appointments,
warning signs, recovery, a teach-back quiz, and a discharge check that reports
what the paperwork never explained.

The AI surfaces gaps. A human - the patient's own care team - acts on them.
The system never takes clinical responsibility, and every screen says so.

## 2. Accuracy results

Measured over **68 pipeline outputs** from the corpus of 106 real
de-identified discharge summaries. Full detail and the script that produces
it: `evaluation/corpus_accuracy_report.md`,
`scripts/corpus_accuracy_report.py`.

### 2.1 Readability

The product claim is a sixth-grade reading level. Flesch-Kincaid grade,
logged for every patient-facing output:

| Section | Mean grade | Worst | At or under 6.0 |
|---|---|---|---|
| What happened | 3.74 | 6.29 | 61/63 |
| Medications | 4.12 | 6.33 | 60/61 |
| Recovery | 4.32 | 5.58 | 59/59 |
| Warning signs | 4.53 | 5.89 | 56/56 |

**99% of 239 outputs meet the target**, mean grade 4.17.

Three agents were fixed on 15-16 Aug after failing it, each for a different
reason, and each re-measured afterwards. The recurring cause is worth
recording: in all three cases the prompt's own worked example violated the
prompt's own rules, and the model copied the example.

### 2.2 Grounding against the source document

| Check | Result |
|---|---|
| Medication names in the output that the source does not contain | **0 of 68** |
| Outputs containing a number absent from the source | 50 of 68 |

Zero invented medications is the result that matters most: Agent 1 fabricating
a drug name is the worst failure available to this system, and it does not
happen across 68 real documents.

The number findings are **not** random fabrication, and the report classifies
them rather than counting them:

- **51 occurrences are clinical thresholds the prompts supply** - "fever over
  101 F", "100.4 F". Standard guidance, but presented to the patient as though
  their own paperwork said it.
- **40 occurrences are activity targets the model invents** - "walk 15 minutes
  each day", "do not bend your new knee more than 90 degrees". The Agent 4
  prompt *requires* one specific goal per week, so when the source sets none,
  the model supplies a number. The requirement causes the invention.

Both are defensible as general patient education and indefensible as
instructions attributed to a specific discharge document. A knee protocol
differs between surgeons; a fever threshold differs for an immunocompromised
patient. **This is the first question for clinical review, not a decision to
make in a prompt file.**

### 2.3 What the source documents actually contain

| Field | Documents containing it |
|---|---|
| Follow-up appointments | 88% |
| Medications | 87% |
| Activity or diet restrictions | 40% |
| Discharge date | 37% |
| Red-flag symptoms | 25% |

Real discharge paperwork is missing sections constantly. This is the evidence
behind treating an absent section as a property of the document rather than a
failure of the pipeline - a distinction the app got wrong until 15 Aug, when
it told patients "our reading service was busy" about sections the hospital
never wrote.

### 2.4 Safety

The adversarial audit (task 4.1) passed **6 of 6** cases on 31 Jul 2026,
covering prompt injection and corrupted input, after finding and fixing a real
injection hole in Agent 1. Two defects in the audit *harness* were fixed
first: it had reported a pass on a run where every LLM call failed.

An end-to-end verification of the deployed service
(`scripts/verify_live_service.py`) runs **28 checks**, including that one
patient's session cannot be read from another's. All pass against the current
revision.

## 3. Comprehension lift

**INCOMPLETE - needs the tester cohort (task 2.6).**

The mechanism is built, deployed and measured server-side: an identical
five-question quiz before and after reading, with the delta computed on the
server rather than in the app, stored in Neon.

What the database currently holds:

| Measure | Value |
|---|---|
| Quiz scores recorded | 14 (9 pre, 5 post) |
| Mean pre-reading score | 33.3% |
| Mean post-reading score | 90.0% |

That is a **+56.7 point** difference, and it must be read with care: these are
development and verification sessions, not patients. The sample is tiny, the
pre and post sets are not paired, and several were generated deliberately
wrong to test the scoring path. **It demonstrates the instrument works. It is
not evidence about patients.**

The literature baseline the project targets is ~13% full comprehension of
discharge instructions, against a 50-70% goal. Establishing where this system
actually lands requires the tester cohort, which is the single outstanding
acceptance item for Checkpoint 2.

## 4. Telemetry

Recorded in Neon PostgreSQL. Per the repository's own rule, the database
stores structured fields, hashes and metadata only - **never agent prose and
never document text**.

| Measure | Value |
|---|---|
| Analyses recorded | 660 |
| Distinct sessions | 533 |
| Quiz scores | 14 |

Pipeline status across all recorded analyses: 309 `partial`, 204 `complete`,
147 `complete_with_warnings`. The `partial` count is inflated by history: until
15 Aug the pipeline classified a document missing medications or red flags as
`partial`, which on real paperwork is the common case. Post-fix runs put
`complete_with_warnings` in the majority, as section 2.3 predicts.

Readability is additionally logged per output to `evaluation/fk_log.csv`.

## 5. Known limitations

Stated plainly, in the order a reviewer would care about them.

1. **No clinician verification yet.** The review portal, the rubric and the
   frozen outputs are ready; the reviewers are not assigned. Until that
   happens, no clinical accuracy claim in this report has been checked by a
   clinician.
2. **No real patient or tester data.** Every number here comes from
   de-identified corpus documents and development sessions.
3. **Generic clinical numbers appear in patient-facing text** (section 2.2).
   Unresolved by design, pending clinical review.
4. **iOS distribution is limited.** No paid Apple account means no TestFlight:
   an iPhone build lasts 7 days and needs the device in hand. Android ships as
   a signed direct-install APK.
5. **Single-instance serving.** The PDF and simulator stores are per-process,
   so the service is pinned to one instance. Multi-instance serving needs a
   shared store (GCS or Redis) and is not wired.
6. **Per-case audio is not generated.** The endpoint, both players, the
   generator and the silent text-only fallback all work; generation is blocked
   on free-tier TTS quota. Five diagnoses are queued.
7. **No backup demo recording.** The pre-flight checks in
   `docs/DEMO_SCRIPT.md` are the current mitigation.
8. **The corpus is third-party sourced.** MTSamples transcriptions with
   identifiers removed, rebuilt from a script rather than committed. Findings
   generalise to that corpus, not necessarily to any particular hospital's
   paperwork.

## 6. What would make this production-ready

Not a roadmap, an honest list of what stands between this and real patients:

- Clinician sign-off on the escalation tiers and on the generic-numbers
  question in 2.2
- A shared session store, so it can serve more than one instance
- Real comprehension measurement on a tester cohort large enough to mean
  something
- A resolved answer on liability and provider review, which Frank raised at
  the 5 Aug demo and which is a business question before it is a technical one
- EHR integration via FHIR, which Frank confirmed is reachable through
  existing connections
