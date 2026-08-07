# Questions for Dr. Leibowitz - clinical validation of DischargeIQ

**Status: draft v2, for Tanuj and Steve to work through before it reaches
Dr. L.** Not yet a final list. Rev. 6 August 2026.

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

**Time:** 45 minutes. Sections A, B and C block work.

**The trim decision, for Tanuj and Steve:** 21 questions will not fit in 45
minutes - realistically 10 to 12 will. The proposal is to take **A, B and C**
to Dr. L (13 questions, all of which block a build or a review decision) and
route **D** (liability, what gates a pilot) to Steve and Frank instead, since
it is as much a legal and governance question as a clinical one. **E and F**
are worth asking but nothing stops if they go unanswered this round.

## What changed in v2 - Frank's suggestions, 5 August

Three of Frank's suggestions are now built, which turns each of them into a
question a clinician has to answer:

| Frank's suggestion | Built | New questions |
|---|---|---|
| Define a rubric for discharge-instruction validation | Review rubric running in the portal | 2 and 3 sharpened |
| Ask the patient what they want to learn, then gamify that | Learning goals + a four-rung self-rating ladder | **9, 10, 11** |
| An AI companion that reads sections aloud | Voice chat: ask by microphone, answers spoken, "read me my medications" opens and reads that tab | **12, 13** |
| Advocate pilot - 75 patients, nurse managers | Scoped, not started | **1**, plus `docs/ADVOCATE_PILOT_BRIEF.md` |

Everything in **section C is new**; sections A, B, D, E and F are the
previously circulated list, renumbered to make room.

Frank's remaining items are not clinical questions and are tracked elsewhere:
the Ken / Dr. Meyer / Dr. Carlson introductions, and the public-release value
proposition and revenue model.

Companion docs: `docs/VALIDATION_RUBRIC.md` (the rubric instrument itself),
`docs/ADVOCATE_PILOT_BRIEF.md` (the pilot scoping),
`docs/KEN_GAMIFICATION_BRIEF.md` (pre-read for Ken),
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

## C. The layers built from Frank's suggestions - are they clinically sound?

These are new since the 5 August meeting. Each one was Frank's idea, is now
built, and needs a clinician to say whether it should stay as built.

### 9. Letting the patient choose what to learn - does that risk what matters?

**Built:** after the first analysis the app asks *what do you most want to
understand?* and the patient picks from five topics. Their choice reorders the
reading journey, drives the quests, and gives that topic extra quiz questions.

**Guard already in place:** warning signs are never dropped from the quiz,
whatever they choose, and nothing is hidden - only reordered.

**Ask:** is patient-led ordering safe, or is there a topic a patient must be
walked through whether or not they asked for it? Is our warning-signs guard
the right one, or should medications be protected the same way?

**Either way:** the guard list is one line of prompt text; the question is
which topics belong on it.

### 10. Does a self-rating ladder measure anything real?

**Built:** for each chosen topic the patient rates themselves before reading
and again after, on four rungs - *not yet / the gist / I could explain it /
I could teach it.* The movement between the two is what we report.

**The obvious objection:** patients routinely overestimate what they
understood, which is the reason teach-back exists at all. A self-rating could
therefore measure confidence rather than comprehension.

**Ask:** is self-rating worth collecting alongside the quiz, or does it invite
a claim we cannot support? We already hold both numbers - the quiz measures
recall, the ladder measures confidence - and the **gap between them** may be
the more honest signal.

**Either way:** we keep collecting both and report whichever he says is
defensible. What we will not do is report the self-rating as comprehension.

### 11. Is "I could explain this to someone at home" the right bar?

**Built:** rung 2 of four is treated as the threshold for a goal being met,
chosen because it mirrors what a nurse asks at the bedside. Rung 3, *"I could
teach this and act on it without checking"*, is aspirational and never
required.

**Ask:** is that the right rung to treat as sufficient, and is the wording
recognisable as teach-back to someone who does it daily?

### 12. A voice reading clinical content aloud

**Built:** the patient can ask a question by microphone and hear the answer
spoken, and can say *"read me my medications"* to have that section read out.
Speech recognition and playback are handled on the phone; no audio is recorded
or sent anywhere.

**Ask:** does hearing a discharge summary carry a risk that reading it does
not - a spoken dose misheard, or a warning sign that lands differently aloud?
Is there any section that should **never** be read aloud unattended?

**Either way:** sections can be excluded from read-aloud individually. We have
already excluded the quiz and the AI-review tab, on the grounds that reciting
the app's own gap analysis at a patient is not useful.

### 13. Voice in a room with other people

**Built:** playback goes to the phone's speaker or headphones, whatever the
patient has set. There is no warning before it starts speaking.

**Ask:** does an app that reads a diagnosis out loud need to say so before it
starts - a hospital ward, a waiting room, a shared house? Is that a privacy
question we should be handling, or are we overthinking a feature patients
would simply turn off?

---

## D. Liability, scope, and what a health system would require

### 14. Does the responsibility framing hold up?

The framing is: the AI surfaces, a human decides. The app assists,
summarizes, and educates. It does not diagnose, advise, or triage, and every
gap it finds is labelled as something to discuss with the care team.

**Ask:** does that hold up in practice, and what specifically would have to
change before a health system would put it in front of patients?

### 15. What gates a pilot?

**Ask:** IRB, legal review, BAA, clinical governance sign-off - which of these
actually gate a patient-facing pilot, and in what order?

**Why now:** we would rather start the slowest one immediately than discover
it in September. The Advocate pilot brief scopes both a
nurse-reviewers-only option that could start in days and a patient-facing
option that depends entirely on these answers.

---

## E. Population fit

### 16. Pediatric handling - anything beyond the voice?

When a summary belongs to a young child, every agent, the chat, and the quiz
now write to the **caregiver** instead of addressing the infant as "you"
(another real-corpus catch). 7 of the 106 corpus documents are pediatric; no
false positives on adult documents.

**Ask:** Is there anything clinically distinct about pediatric discharge -
content, escalation thresholds, follow-up emphasis - that should change
beyond the addressee?

### 17. Is 6th-grade reading level the right target?

Every output is scored with Flesch-Kincaid and must land at grade ≤ 6.0.

**Ask:** Right target for this population? Any domain (medications,
escalation) where simplifying that far risks losing clinically necessary
precision?

### 18. Who should NOT use this app?

Solo patients with cognitive impairment, non-English speakers (Spanish is a
stretch goal, currently cut), low vision, no smartphone.

**Ask:** Are there patient groups where you would actively advise against
this tool rather than just noting its limits?

---

## F. The measurement story

### 19. Does the teach-back quiz measure what we claim?

Five non-leading multiple-choice questions generated from the patient's own
document, taken before reading (no hints, no score shown) and after. The
before/after delta is the headline metric (target: ~13% baseline
comprehension → 50-70%).

**Ask:** Does a 5-question MCQ delta credibly stand in for teach-back as
clinicians practice it? What would make the questions clinically meaningful
rather than trivia?

### 20. The AI Review gap severities

Agent 6 simulates a confused patient and flags questions the document never
answers, graded critical / moderate / minor, surfaced to the care team - the
AI surfaces gaps, a human decides.

**Ask:** Do those three severity levels map to how you would triage
documentation gaps? What would make this tab useful to a discharge
coordinator rather than noise?

### 21. The mood check-in threshold

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
