# Questions for Dr. Leibowitz - clinical validation of DischargeIQ

Dr. Leibowitz is the clinician validator for this project. These are the
application questions only a clinician can answer, each with the context he
needs to answer it and what is already built.

**Consolidated list.** Per Steve's plan, team questions are gathered and
reviewed internally first, so this is the single list rather than several
overlapping ones. A question earns a place here only if (a) it changes what we
build or ship, and (b) nobody on the team can answer it without clinical
authority.

**How each item is written:** the decision at stake, what is already built and
why, the ask, and what we do with either answer. That last part is
deliberate - it shows we are asking in order to act.

**Time:** 45 minutes. Sections A and B block work. Drop D if it runs short.

Companion docs: `docs/VALIDATION_RUBRIC.md` (the rubric instrument itself),
`docs/MEETING_PREP_2026-08-03.md` (meeting context), `ui/clinician_review.py`
(the review portal he would use).

---

## A. The clinician review itself (blocks Checkpoint 4)

### 1. Are you the right reviewer profile - and if not, who is?

The plan assumes a **discharge nurse or discharge coordinator** is the right
reviewer, rather than a physician, on the grounds that discharge workflow
expertise is what the verification needs. Effort is 10-15 minutes per
document, 1-2 hours total, self-paced, through a web portal that is already
built.

**Ask:** Is that the right profile? Would you review a sample yourself, or
recommend who should?

**Either way:** if nurse or coordinator, recruiting proceeds through Advocate
(see `docs/ADVOCATE_PILOT_BRIEF.md`). If physician, the sample shrinks and the
timeline moves - and we need that now, not at Checkpoint 4.

### 2. Is "judge only what the source contained" the right rubric?

Reviewers score 0-5 on **fidelity to the source document**, not against an
ideal summary. Real discharge paperwork is incomplete: across our 106-document
de-identified corpus, warning signs appear in only 34% of documents,
discharge medications in 62%, follow-up in 69%. The rubric therefore says:
content absent from both source and output is not a penalty; content in the
output that is NOT in the source is the serious failure.

**Ask:** Is that the right instruction, or should absent content count
against the output anyway?

**This is the most consequential rubric decision.** It determines whether we
are measuring our system or measuring US discharge documentation. It is also
the call most worth overriding us on.

### 3. Where does the pass bar sit?

The gate is currently **median ≥ 4.0 across all documents, plus zero
hallucination flags** - a hallucination being any medication, dose, or
diagnosis in the output that is not in the source.

**Ask:** is median ≥ 4.0 the right bar for a patient-facing tool, and is
zero-tolerance on invented clinical content the right absolute?

**Either way:** a bar changed after scoring is not evidence, so we need this
before the review starts. Full rubric in `docs/VALIDATION_RUBRIC.md`, which
also lists the two remaining open decisions (reviewer profile, and whether
"invented content" is the right wording for reviewers).

### 4. What would make you distrust this output?

The most useful question of all. It surfaces the failure mode worth testing
BEFORE the formal review starts, not after.

**Ask:** When you read an AI explanation of a discharge summary, what single
thing would make you stop trusting it?

---

## B. Safety boundaries already built one way - tell us if the call was wrong

### 5. The general-safety fallback line

When a document lists **no warning signs**, the app shows generic advice -
call 911 for chest pain, trouble breathing, heavy bleeding, fainting, sudden
weakness - clearly labelled *"general advice, not from your document."*
Given the 34% figure above, this fires on most real documents.

**Ask:** Is showing that safer than showing nothing, or does ANY
non-document clinical content cross a line?

**If it crosses a line:** we ship an empty state instead, and the 34% becomes
a finding we report rather than a gap we fill.

### 6. The escalation three-tier decision tree

Warning signs are presented in three tiers (call 911 / go to the ER today /
call your doctor), with a hard rule of zero ambiguous language - no "may
need", no "consider calling". Every escalation output is read manually before
shipping.

**Ask:** Are three tiers the right structure? Is there a symptom class where
tiering itself is dangerous and the app should only ever say "call 911"?

### 7. Medication explanations without medication advice

Agents explain **why each drug was prescribed** in plain language but are
hard-blocked from ever advising to stop, change, or re-dose a medication.
Inpatient-only drugs are excluded from the take-home list (a real bug the
real-document corpus caught, now fixed).

**Ask:** Is "explain the why, never touch the what" a safe boundary? Anything
you would add to the block list (interactions? side-effect lists?)?

### 8. The grounded chat's refusal behavior

The chat answers only from the uploaded document and refuses everything else.
If a patient types an urgent symptom question ("my chest hurts right now"),
it cannot diagnose - it can only point to the warning-signs tab and the
general 911 line.

**Ask:** Is refusal-plus-redirect the right behavior for an app a sick person
can type into at 2am, or does that interaction need something stronger?

---

## C. Liability, scope, and what a health system would require

### 9. Does the responsibility framing hold up?

The framing is: the AI surfaces, a human decides. The app assists,
summarizes, and educates. It does not diagnose, advise, or triage, and every
gap it finds is labelled as something to discuss with the care team.

**Ask:** does that hold up in practice, and what specifically would have to
change before a health system would put it in front of patients?

### 10. What gates a pilot?

**Ask:** IRB, legal review, BAA, clinical governance sign-off - which of these
actually gate a patient-facing pilot, and in what order?

**Why now:** we would rather start the slowest one immediately than discover
it in September. The Advocate pilot brief scopes both a
nurse-reviewers-only option that could start in days and a patient-facing
option that depends entirely on these answers.

---

## D. Population fit

### 11. Pediatric handling - anything beyond the voice?

When a summary belongs to a young child, every agent, the chat, and the quiz
now write to the **caregiver** instead of addressing the infant as "you"
(another real-corpus catch). 7 of the 106 corpus documents are pediatric; no
false positives on adult documents.

**Ask:** Is there anything clinically distinct about pediatric discharge -
content, escalation thresholds, follow-up emphasis - that should change
beyond the addressee?

### 12. Is 6th-grade reading level the right target?

Every output is scored with Flesch-Kincaid and must land at grade ≤ 6.0.

**Ask:** Right target for this population? Any domain (medications,
escalation) where simplifying that far risks losing clinically necessary
precision?

### 13. Who should NOT use this app?

Solo patients with cognitive impairment, non-English speakers (Spanish is a
stretch goal, currently cut), low vision, no smartphone.

**Ask:** Are there patient groups where you would actively advise against
this tool rather than just noting its limits?

---

## E. The measurement story

### 14. Does the teach-back quiz measure what we claim?

Five non-leading multiple-choice questions generated from the patient's own
document, taken before reading (no hints, no score shown) and after. The
before/after delta is the headline metric (target: ~13% baseline
comprehension → 50-70%).

**Ask:** Does a 5-question MCQ delta credibly stand in for teach-back as
clinicians practice it? What would make the questions clinically meaningful
rather than trivia?

### 15. The AI Review gap severities

Agent 6 simulates a confused patient and flags questions the document never
answers, graded critical / moderate / minor, surfaced to the care team - the
AI surfaces gaps, a human decides.

**Ask:** Do those three severity levels map to how you would triage
documentation gaps? What would make this tab useful to a discharge
coordinator rather than noise?

### 16. The mood check-in threshold

Optional daily mood check-in; several rough days in a row surfaces a
"consider contacting your care team" nudge. A rough day makes the app ask
LESS of the patient, never more.

**Ask:** Useful signal or overreach? Is a several-day threshold clinically
sensible, and what should the nudge actually say?

---

## Do not ask

- Anything about models, hosting, or architecture. He is not being consulted
  as a technologist, and it burns credibility.
- "Do you like it?" - produces politeness, not information.
- Anything the team can settle itself. That was the point of consolidating.

## Capture verbatim

Every "I would never", the exact wording of anything he corrects, and any
hesitation - hesitation is a finding. Before leaving, write down the one thing
he said that you did not want to hear. That is usually the one worth acting
on.
