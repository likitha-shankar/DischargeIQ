# Gold-standard annotation schema

**Closes:** Liebovitz item 3.4 (schema half) and Week 7 of his milestone plan.
**Status:** schema defined, no documents annotated yet.
**Owner:** Likitha Shankar. Annotation is performed by a clinician.

---

## Why this exists, and what it unblocks

Every accuracy number this project currently reports measures one leg:
**extraction → patient-facing output**. The extraction record is the reference,
so no human is needed, and `evaluation/corpus_accuracy_report.md` states that
scope openly - 99.6% medication recall means *of what Agent 1 extracted*, not
of what the document contained.

The other leg, **source document → extraction**, cannot be measured without a
human reading the document and writing down what is actually in it. That is
what this schema is for.

Until it exists, four things are unavailable:

- true precision and recall (the reported numbers are an upper bound - a
  medication Agent 1 never saw cannot appear as a miss)
- per-stratum accuracy that means anything (item 3.1)
- any confidence interval, since there is no ground truth to interval against
- Agent 6's agreement with human judgement (it currently grades a language
  model with a language model)

**Errors of omission are the target.** A dropped medication produces a clean,
confident, wrong document, and nothing downstream can detect it. The schema is
therefore built around *finding what is missing*, which is why the annotator
reads the source first and the system output second - and, for the primary
pass, not at all.

---

## The annotation task, in one paragraph

Read one discharge document. Write down every medication, dose, follow-up
appointment, and warning sign the document actually states, with the text you
read it from. Do not consult the system output. That is the whole task.

Estimated **12-18 minutes per document** after the first three. For 25
documents, roughly **6-7 clinician hours**, splittable across sessions.

---

## Ground rules

1. **Annotate the document, not the patient.** If the document does not say
   it, it is not in the annotation - however obvious the clinical inference.
   The system is forbidden to infer; the ground truth must hold the same line
   or it will score correct inferences as fabrications and true omissions as
   correct.
2. **Blind to system output on the first pass.** An annotator who has seen the
   extraction anchors to it and stops looking. Adjudication (below) is where
   the two meet.
3. **Quote, do not paraphrase.** Every entity carries the verbatim span it
   came from. This is what makes a disagreement resolvable months later.
4. **Absent and empty are different.** A document with no medication section
   is not the same as one whose section is present and empty. Both occur.
5. **Uncertainty is recordable.** `uncertain: true` with a note is always
   available and is never a failure. A forced binary produces confident
   garbage.

---

## Record format

One JSON file per document, `evaluation/annotations/{document_id}.json`.

Not `evaluation/gold/`: `evaluation/golden/` already exists for the
golden-file regression, and two directories one letter apart holding
different things is a trap for whoever comes next. The annotations are
clinical text and are gitignored for the same reason the corpus is.

```json
{
  "document_id": "mtsamples_014",
  "annotator": "initials or role, never a patient identifier",
  "annotated_at": "2026-09-15",
  "source_stratum": "dictated",
  "minutes_spent": 14,

  "sections_present": {
    "medications": true,
    "follow_up": true,
    "warning_signs": false,
    "activity_or_diet": true,
    "discharge_date": true
  },

  "medications": [
    {
      "name": "Furosemide",
      "dose": "40 mg",
      "frequency": "twice daily",
      "duration": null,
      "status": "new",
      "span": "Furosemide 40 mg PO BID",
      "uncertain": false,
      "note": null
    }
  ],

  "follow_up_appointments": [
    {
      "provider": "Dr. Chen",
      "specialty": "Cardiology",
      "date": "2 weeks",
      "reason": "medication titration",
      "span": "Follow up with Dr. Chen (Cardiology) in 2 weeks",
      "uncertain": false,
      "note": "date is relative in the source; do not resolve it"
    }
  ],

  "warning_signs": [
    {
      "text": "weight gain of more than 3 pounds in one day",
      "span": "Call if you gain more than 3 lbs in a day",
      "threshold_value": "3 lbs/day",
      "uncertain": false
    }
  ],

  "annotator_notes": "Free text. Anything that made the document hard to read."
}
```

### Field rules that decide close calls

| Situation | Rule |
|---|---|
| Same drug listed twice (admission and discharge lists) | Annotate the **discharge** list only; note the duplication |
| Drug named with no dose | Annotate it, `dose: null`. A named drug with no dose is a real and common state |
| "Continue home medications" with no list | `sections_present.medications: true`, zero entries, note it. This is the hardest true negative in the corpus |
| Relative date ("in 2 weeks") | Record verbatim. **Never resolve to a calendar date** - the system is forbidden to, so resolving it here would score correct behaviour as wrong |
| Warning sign with a number | Record `threshold_value` separately. Invented thresholds were the measured fabrication mode; separating them makes that directly checkable |
| Symptom mentioned in narrative, not in a warning list | Annotate, `uncertain: true`, note where it appeared |
| Illegible or OCR-mangled | `uncertain: true` with the raw text in `note`. Do not guess |

---

## Sample size and what it buys

**25 documents** is the Week 8 target and is enough to find systematic
failures, not to place tight intervals on them. Stated plainly so the eventual
report does not overclaim:

Wilson score intervals, at a 95% recall point estimate and ~5 medications per
document:

| Documents | Medication entities | 95% CI on 95% recall |
|---|---|---|
| 25 | ~125 | **89.7 - 97.7%** |
| 50 | ~250 | 91.6 - 97.1% |
| 100 | ~500 | 92.7 - 96.6% |

Useful, and visibly not a precise claim. Quadrupling the annotation effort
buys about three percentage points of width.

Diminishing returns arrive quickly, which is the argument for spending
clinician time on **stratum coverage** rather than depth: 25 documents spread
across four source formats is worth more than 100 dictated ones, because a
single blended number cannot show one format failing while another passes.

---

## Stratum assignment

Every annotated document records its `source_stratum`, one of:

| Stratum | What it is | Have it? |
|---|---|---|
| `dictated` | Transcribed narrative (the MTSamples corpus) | **106 documents** |
| `structured_export` | Clean EHR after-visit summary | **none - needs a site** |
| `scanned_fax` | Real scan or fax, real OCR damage | **none - simulated only** |
| `multi_page` | Long multi-section discharge packet | **none** |

The current corpus is **one stratum**, and the fax figures in
`evaluation/fax_stratum_report.md` come from *simulated* degradation of
already-clean text - that report says so itself and calls every figure a lower
bound. Annotating 25 more dictated documents would improve nothing about
stratum coverage. **Real documents in the other three strata are the blocker,
and they need a site relationship, not developer time.**

---

## Adjudication and agreement

1. **Pass 1** - clinician annotates blind.
2. **Pass 2** - `scripts/score_against_gold.py` matches the
   annotation against Agent 1's extraction and emits three lists: matched,
   missed by the system, and present in the system but absent from the
   annotation.
3. **Pass 3** - a human resolves every disagreement into one of:
   - `system_miss` - a true omission, the number that matters
   - `system_fabrication` - present in the output, absent from the source
   - `annotation_miss` - the annotator missed it; corrected in the gold file
   - `boundary` - both are defensible ("Lasix" vs "furosemide", one appointment
     recorded as two). These are counted and reported separately, never folded
     silently into either side

**Entity matching is normalised before comparison** - case, whitespace,
punctuation, and a generic/brand name map. Without that, "Lasix 40mg" and
"furosemide 40 mg" score as one miss and one fabrication, which is two errors
where there is none.

**Double-annotate 5 of the 25** with a second reader and report
inter-annotator agreement. Without it, the gold standard is one person's
reading presented as truth, and disagreement between two clinicians on what a
discharge document says is itself a finding worth having.

---

## What this does NOT establish

- **Comprehension.** Entity recall says the medication reached the page. It
  says nothing about whether the patient understood it. That is the teach-back
  study (item 2.1), and this schema is not a substitute for it.
- **Clinical appropriateness.** Whether the discharge plan was *correct* is
  outside scope. The measurement is faithfulness to the document.
- **Agent 6 validation.** Agent 6's gap scores can be compared against these
  annotations once they exist, but Liebovitz's actual ask is agreement with
  **human teach-back results**, which needs the study, not this.

---

## Related

- `evaluation/corpus_accuracy_report.md` - current numbers and their stated scope
- `evaluation/fax_stratum_report.md` - the simulated stratum and its limits
- `docs/VALIDATION_RUBRIC.md` - the 0-5 output-quality scale, a different measurement
- `docs/extraction_schema.json` - the field contract being annotated against
