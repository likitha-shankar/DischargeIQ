# Questions for Dr. Leibowitz - clinical validation of DischargeIQ

Dr. Leibowitz is the clinician validator for this project. These are the
application questions only a clinician can answer, each with the context he
needs to answer it and what is already built. Ordered so the review-blocking
questions come first.

Companion docs: `docs/MEETING_PREP_2026-08-03.md` (meeting context),
`ui/clinician_review.py` (the review portal he would use).

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

### 2. Is "judge only what the source contained" the right rubric?

Reviewers score 0-5 on **fidelity to the source document**, not against an
ideal summary. Real discharge paperwork is incomplete: across our 106-document
de-identified corpus, warning signs appear in only 34% of documents,
discharge medications in 62%, follow-up in 69%. The rubric therefore says:
content absent from both source and output is not a penalty; content in the
output that is NOT in the source is the serious failure.

**Ask:** Is that the right instruction, or should absent content count
against the output anyway? Where would you put the pass bar (currently
median ≥ 4.0)?

### 3. What would make you distrust this output?

The most useful question of all. It surfaces the failure mode worth testing
BEFORE the formal review starts, not after.

**Ask:** When you read an AI explanation of a discharge summary, what single
thing would make you stop trusting it?

---

## B. Safety boundaries already built one way - tell us if the call was wrong

### 4. The general-safety fallback line

When a document lists **no warning signs**, the app shows generic advice -
call 911 for chest pain, trouble breathing, heavy bleeding, fainting, sudden
weakness - clearly labelled *"general advice, not from your document."*

**Ask:** Is showing that safer than showing nothing, or does ANY
non-document clinical content cross a line?

### 5. The escalation three-tier decision tree

Warning signs are presented in three tiers (call 911 / call your doctor
today / mention at next visit), with a hard rule of zero ambiguous language -
no "may need", no "consider calling". Every escalation output is read
manually before shipping.

**Ask:** Are three tiers the right structure? Is there a symptom class where
tiering itself is dangerous and the app should only ever say "call 911"?

### 6. Medication explanations without medication advice

Agents explain **why each drug was prescribed** in plain language but are
hard-blocked from ever advising to stop, change, or re-dose a medication.
Inpatient-only drugs are excluded from the take-home list (a real bug the
real-document corpus caught, now fixed).

**Ask:** Is "explain the why, never touch the what" a safe boundary? Anything
you would add to the block list (interactions? side-effect lists?)?

### 7. The grounded chat's refusal behavior

The chat answers only from the uploaded document and refuses everything else.
If a patient types an urgent symptom question ("my chest hurts right now"),
it cannot diagnose - it can only point to the warning-signs tab and the
general 911 line.

**Ask:** Is refusal-plus-redirect the right behavior for urgent messages, or
does an app that a sick person can type into need something stronger?

---

## C. Population fit

### 8. Pediatric handling - anything beyond the voice?

When a summary belongs to a young child, every agent, the chat, and the quiz
now write to the **caregiver** instead of addressing the infant as "you"
(another real-corpus catch). 7 of the 106 corpus documents are pediatric; no
false positives on adult documents.

**Ask:** Is there anything clinically distinct about pediatric discharge -
content, escalation thresholds, follow-up emphasis - that should change
beyond the addressee?

### 9. Is 6th-grade reading level the right target?

Every output is scored with Flesch-Kincaid and must land at grade ≤ 6.0.

**Ask:** Right target for this population? Any domain (medications,
escalation) where simplifying that far risks losing clinically necessary
precision?

### 10. Who should NOT use this app?

Solo patients with cognitive impairment, non-English speakers (Spanish is a
stretch goal, currently cut), low vision, no smartphone.

**Ask:** Are there patient groups where you would actively advise against
this tool rather than just noting its limits?

---

## D. The measurement story

### 11. Does the teach-back quiz measure what we claim?

Five non-leading multiple-choice questions generated from the patient's own
document, taken before reading (no hints, no score shown) and after. The
before/after delta is the headline metric (target: ~13% baseline
comprehension → 50-70%).

**Ask:** Does a 5-question MCQ delta credibly stand in for teach-back as
clinicians practice it? What would make the questions clinically meaningful
rather than trivia?

### 12. The AI Review gap severities

Agent 6 simulates a confused patient and flags questions the document never
answers, graded critical / moderate / minor, surfaced to the care team - the
AI surfaces gaps, a human decides.

**Ask:** Do those three severity levels map to how you would triage
documentation gaps? What would make this tab useful to a discharge
coordinator rather than noise?

### 13. The mood check-in threshold

Optional daily mood check-in; several rough days in a row surfaces a
"consider contacting your care team" nudge. A rough day makes the app ask
LESS of the patient, never more.

**Ask:** Useful signal or overreach? Is a several-day threshold clinically
sensible, and what should the nudge actually say?
