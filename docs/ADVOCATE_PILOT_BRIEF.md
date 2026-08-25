# Advocate pilot - scoping brief

**Origin:** Frank raised a possible pilot with Advocate LLC - roughly 75
patients, nurse managers involved, as a route to rubric testing and clinical
validation.

**Status:** unscoped. Nobody has written down what it would actually involve,
so this is a first pass at the shape, the honest constraints, and the
questions that decide whether it is feasible inside the summer.

**Bottom line up front:** there are two very different pilots hiding in this
idea, and they have completely different requirements. Choosing between them
is the first decision.

---

## 1. The two pilots

### Option A - nurse managers as reviewers (no patients)

Nurse managers score de-identified discharge documents in the existing review
portal. No patient uses the app. No patient data leaves anywhere.

- **Gives us:** clinical validation, rubric testing, exactly the Checkpoint 4
  evidence we need.
- **Needs:** access codes and about 2 hours per reviewer.
- **Blocked by:** almost nothing. Could start in days.
- **Data posture:** our own de-identified corpus, no Advocate data at all.

### Option B - 75 patients actually using the app

Real patients receive their own discharge summary through DischargeIQ.

- **Gives us:** real comprehension data, real engagement data, the strongest
  possible outcome story.
- **Needs:** IRB, BAA, legal review, clinical governance, consent process, a
  compliant data path, patient support, and a way to handle someone who types
  a real symptom into the chat at 2am.
- **Blocked by:** all of the above. Months, not weeks, and mostly not in our
  control.

**Recommendation: A now, B scoped in parallel.** Option A produces the
validation evidence the summer actually requires. Option B is the right
ambition, but treating it as a summer deliverable puts the checkpoint at the
mercy of another organization's IRB calendar.

---

## 2. What Option A would look like

| | |
|---|---|
| **Participants** | 2-4 nurse managers or discharge coordinators |
| **Effort** | 10-15 min per document, ~2 hours total, self-paced |
| **Material** | 50 frozen outputs from our de-identified corpus |
| **Instrument** | Existing portal, 0-5 fidelity + invented-content flag |
| **Data leaving Advocate** | None |
| **Data entering Advocate** | De-identified documents only |
| **Output** | Median score, flag count, fix worklist, written comments |
| **Lead time** | Days, once names are identified |

Reviewers are told to judge only what the source contained - see
`docs/VALIDATION_RUBRIC.md`, which is the instrument itself.

---

## 3. What Option B would require, honestly

Listing this so nobody is surprised later, and so the slow items can start
early if the answer is yes.

**Regulatory and legal**
- IRB determination - is this research, or quality improvement? Different
  paths, very different timelines.
- BAA covering the LLM provider. We have a Vertex AI path under GCP BAA
  specifically for this; it is the required path for any real patient data.
- Legal review of patient-facing AI content, including the general-safety
  fallback line.
- Clinical governance sign-off.

**Clinical safety**
- What happens when a patient types an urgent symptom into the chat. Current
  behavior is refuse and redirect. A real deployment likely needs an agreed
  escalation path, and someone at Advocate has to own it.
- Who the patient calls when the app is wrong.
- Explicit statement that the app does not replace discharge teaching.

**Operational**
- Who hands the patient the app, at what moment in the discharge process.
- Android is required - no paid Apple account means no TestFlight distribution.
- Device access. Patients without smartphones are excluded, which is itself a
  finding worth recording.
- Support when it breaks, out of hours.

**Measurement**
- Consent covering the before/after quiz data.
- Whether nurse managers see engagement data - which turns a comprehension
  tool into a compliance tool, and is a question already on the Dr.
  Liebovitz list (`docs/LIEBOVITZ_CLINICAL_QUESTIONS.md`).

---

## 4. What we can honestly commit to

Stated plainly, because over-promising here is worse than declining:

- **Can:** support Option A immediately; provide the portal, the frozen
  corpus, and the analysis.
- **Can:** run the pipeline through Vertex under BAA if Advocate data is ever
  involved.
- **Can:** ship Android builds for a small cohort.
- **Cannot:** carry IRB or legal work. Solo developer, and those are not
  engineering tasks.
- **Cannot:** provide 24/7 clinical support for a live patient cohort.
- **Cannot:** guarantee an Option B pilot completes inside the summer. The
  timeline belongs to Advocate's review bodies, not to us.

---

## 5. Questions for Frank

1. **A or B?** Is the nurse-manager involvement about reviewing our outputs,
   or supervising patients using the app? The whole brief forks here.
2. Are the 75 patients a real identified cohort, or an illustrative number?
3. Does Advocate treat this as research or quality improvement? Decides
   whether IRB is a determination letter or a full submission.
4. Who at Advocate would own clinical responsibility during a patient pilot?
5. Is there an existing BAA path, or would that start from zero?
6. For Option A, can 2-4 reviewers be named this month? That is the entire
   critical path.
7. Would Advocate want engagement data on their patients - and does that
   change what we should build?

---

## 6. Recommended next step

One short call with whoever at Advocate owns discharge, to settle question 1
and question 6. Everything else follows from those two answers. If the answer
is Option A with named reviewers, this stops being a pilot to plan and becomes
a task to schedule.
