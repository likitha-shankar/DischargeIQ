# DischargeIQ - NABC

**10 September 2026.** Supersedes the numbers in
`docs/MedSynapse_DischargeIQ_NABC_Presentation.pdf` (22 April 2026), which
describes a five-agent pipeline and predates the evaluation corpus entirely.

Every figure below is measured on 106 de-identified real discharge documents
and reproducible from `evaluation/corpus_accuracy_report.md`. Where something
is not measured, it says so.

---

## NEED

A patient is discharged after surgery, exhausted, holding six pages written
for a clinician. At 2am, when something feels wrong, they cannot tell whether
it is expected or an emergency.

- **40-80% of medical information is forgotten immediately**, and roughly half
  of what is retained is retained incorrectly. Kessels RPC, *Journal of the
  Royal Society of Medicine*, 2003 - cited directly in `docs/CITATIONS.md`
  rather than second-hand.
- The paperwork itself is incomplete far more often than people assume. Across
  106 real documents: **only 27% contain any warning-signs section**, and 10%
  name no follow-up appointment at all. The patient cannot know what their
  document failed to tell them.
- Readability alone does not solve it. A sixth-grade reading level measures
  sentence length, not whether anything was understood - independently raised
  by Dr. Liebovitz (22 Aug) and John Trzesniak (10 Sep). **Nobody currently
  measures whether a patient understood their discharge instructions.**

## APPROACH

Six specialist agents behind a router, each restricted to one slice of a
validated extraction record, so no agent can propagate another's error.

1. Extraction - structured fields, every one carrying its source span
2. Diagnosis - what happened, in plain language
3. Medications - each drug and why it was prescribed
4. Recovery - a week-by-week timeline
5. Warning signs - a three-tier escalation guide
6. Discharge Check - an AI patient simulator that finds what the document
   never answered

Plus a **teach-back quiz** that measures comprehension before and after, and
grounded chat that answers only from the document in front of it.

**What makes it defensible rather than just generated:**

- **No fabrication is enforced, not instructed.** Invented numeric thresholds
  ("call if your fever is over 101") appeared in **80% of documents** and are
  now at **0%** - removed after generation, where behaviour is verifiable,
  because four prompt revisions had failed. A threshold the patient's own
  document states is left exactly as written.
- **Every fact is traceable.** Source citation chips point at the verbatim
  span the fact came from, and the original PDF is one tap away.
- **The chat declines rather than guesses.** Measured adversarially: asked for
  an ejection fraction, it answers on a document that states one and declines
  on a document that does not.
- **BAA-covered inference.** Vertex AI under a business associate agreement is
  the required path for real patient data. No consumer API tier is involved.

## BENEFIT

**Measured, on 106 real documents:**

| | |
|---|---|
| Reading grade, mean across 424 outputs | **4.13**, with 99% at or under the sixth-grade target |
| Medication recall, extraction to patient | **99.6%** (532/534) |
| Warning-sign recall | **95.3%** (102/107) |
| Invented clinical thresholds | **80% of documents → 0%** |
| Ungrounded claims that would fail a hard gate | **3%**, down from 85% |

**Stated as a hypothesis, because it is one:** better comprehension is
associated in the literature with lower 30-day readmission. **This project
does not measure readmission and must not claim to.** What it measures is the
comprehension delta - pre-quiz to post-quiz - which is a real number and the
one Dr. Liebovitz asked to see validated in 10-15 patients.

**For the patient:** their medicines, appointments and warning signs in one
place, in words they can read, with what the document left out named
explicitly rather than left as a silence.

**For the provider:** a discharge document that can be checked before it
reaches the patient, and a comprehension score that can be acted on.

## COMPETITION

| | What it does | What it misses |
|---|---|---|
| **Bridge** | Patient engagement on IMO clinical terminology | Does not test whether the patient understood |
| **MyChart / patient portals** | Delivers the document | Delivers it as written - the comprehension problem is untouched |
| **Medisafe, CareZone** | Medication reminders | Medication only; no discharge instructions, no recovery, no escalation |
| **Generic LLM summarisers** | Plain-language rewriting | No grounding guarantee, no provenance, no BAA path, no measurement |

**The gap nobody occupies: measuring whether the patient understood.** Every
competitor above either delivers the document or simplifies it. None closes
the loop. That is the distinction John Trzesniak drew on 10 Sep - readability
is measured everywhere, retention is measured nowhere - and it is the same
distinction Dr. Liebovitz reached independently from the clinical side.

**Deeper competitive analysis is an open action item** (10 Sep, 15:33). This
table is a working position, not a finished market study.

---

## What is not yet true

Stated here because a claim discovered later to be soft costs more than one
disclosed early.

- **No clinician has signed the escalation criteria.** Six templates are
  written and inert; Agent 5 generates all three tiers until one is signed.
- **The comprehension study has zero participants.** The instrument ships; the
  data does not exist. This is the critical path.
- **No gold-standard annotation exists.** Recall figures above measure
  extraction to patient, not source to patient - the schema and scoring tool
  are built and waiting on clinician hours.
- **The corpus is one format.** 106 dictated transcriptions. Clean EHR exports
  and real scanned faxes are needed and require a site.
- **FDA CDS posture is undetermined** and belongs with counsel; the
  engineering fact base is written.
