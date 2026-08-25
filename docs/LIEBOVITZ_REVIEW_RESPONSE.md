# Response to Dr. Liebovitz faculty review

Review document dated **22 August 2026**, worked through on **25 August**
(`docs/DischargeIQ_Review_Liebovitz.docx`, kept out of git by the existing
`docs/*.docx` ignore rule - this markdown file is the tracked record). This file
tracks every item in it: what we do, who owns it, and the commit that closes
it. It is the working artefact for **task 4.2** (clinician sample
verification), which until now had no clinician input recorded against it.

Status key: ✅ done · ◑ in progress · ◻ not started · ⚑ needs a decision from
someone other than the developer

**On the name - RESOLVED 25 Aug 2026.** He was spelled three ways across our
files. The correct spelling is **Liebovitz**: David M. Liebovitz, MD,
Associate Vice Chair for Clinical Informatics and Professor of Medicine at
Northwestern University, board certified in clinical informatics. Every file
and reference has been corrected. Worth noting that clinical informatics is
his actual specialty, which is why the review engages with the architecture
rather than skimming it.

## What he endorsed

The rule-of-one scoping: restricting each agent to an isolated slice of the
extraction record. He called it the strongest design decision, on the grounds
that it prevents error propagation and makes each output independently
auditable. Worth preserving deliberately rather than eroding it for
convenience.

His summary of where we are weak: **evaluation rigor and regulatory framing,
not design.** Every item below sits in one of those two buckets.

---

## Section 2 - Clinical and operations

### ☐ 2.1 Validate readability with teach-back in 10-15 patients ⚑

His point: FK and SMOG penalise unavoidable medical nouns and reward short
sentences that stay opaque. Report the formula score, then prove comprehension.

**He is right, and this is the most important item in the review.** Our entire
quality gate is FK <= 6.0. The 16 Aug corpus run reports mean grade 4.19 with
99% of 220 outputs passing, which proves sentences are short and proves
nothing about understanding.

We are closer than he assumes: the teach-back loop is **already built and
live** (`/quiz/generate`, `/quiz/score`, `quiz_scores` table,
server-side `comprehension_delta`), verified pre 40% -> post 100%. We have
n=1.

**Blocked on the same thing as three other items:** task 2.6 tester
recruiting, which is also what is holding Checkpoint 2. One blocker, four
consequences. Escalate it as one thing.

### ☐ 2.2 Anchor escalation tiers to a physician-signed template

His point: the three-tier guide is the highest-risk output because it gives
triage advice with no clinician in the loop. Make the tiers template-filled
from clinician-authored criteria, not generated.

**Right, and currently unaddressed.** Verified 25 Aug: `escalation_agent.py`
contains **no reference to any template**. The markdown files in
`dischargeiq/templates/` are diagnosis explainers and Agent 5 does not read
them. Agent 5 output is fully generated text.

Our own `CLAUDE.md` hard rule 3 already calls Agent 5 safety-critical and
requires every output to be read manually. He is saying manual review does not
scale and the guarantee belongs in the architecture. Converting Output 4 from
generated to template-filled is a real build, not a prompt edit.

**Assessment: highest-liability item on the list.** Hardest thing to defend to
a reviewer or a regulator as currently built.

### ☐ 2.3 One-page FDA CDS analysis against Cures Act 520(o)(1)(E) ⚑

His point: the exemption narrows for patient-facing, time-critical, directive
output the user cannot independently review.

**Serious and precisely aimed.** Our escalation guide is all four of those at
once. This is not boilerplate risk language.

**Owner: Steve and Frank, plausibly with counsel. Not the developer, and not
drafted by an AI assistant.** `LIEBOVITZ_CLINICAL_QUESTIONS.md` already
proposed routing liability questions to them; this confirms it.

### ◑ 2.4 Source the 40-80% statistic to Kessels (2003) - CITATION FOUND

**Reference confirmed and recorded in `docs/CITATIONS.md`:**
Kessels RPC. "Patients' memory for medical information." *J R Soc Med.*
2003;96(5):219-222. The 40-80% figure is correctly attributed to this paper.

Two further findings from the same source strengthen our case rather than
merely sourcing it, and should go into the deck alongside the headline:

- **Nearly half of what patients do remember is remembered incorrectly.** This
  matters more to us than forgetting: re-handing someone the same document
  does not fix misremembering, which is exactly the gap this product targets.
- **Written summaries improve recall by 20.8%** - direct evidence for the
  product premise, from the same paper as the problem statement.

**Still open, and deliberately left open:** the readmission claim, which he
also flagged. It is currently an association presented as a mechanism, and
fixing it needs either a study measuring readmission against a comprehension
intervention or an honest restatement. Also unsourced: the 13% comprehension
baseline behind the 50-70% target in `CLAUDE.md`. Both are tracked in
`CITATIONS.md` under "Claims that still need a citation".

**Remaining work is manual:** the figure lives in the slide decks and clinical
brief, which are binaries built outside the repository, so the decks have to
be updated to match `CITATIONS.md`.

### ✅ 2.5 Weight omission recall above fluency - DONE 25 Aug 2026

His point: a dropped medication or missed appointment produces a clean,
confident, incorrect document, invisible to the patient. Errors of omission
are the dominant failure mode.

**We do not measure this at all today.** `corpus_accuracy_report.py` measures
readability, and grounding in the *fabrication* direction only: is output
content present in the source. He is pointing at the opposite direction: is
source content missing from the output.

**Implemented.** `scripts/corpus_accuracy_report.py` now reports section 3,
"Omission (extraction against patient-facing output)", locked down by
`dischargeiq/tests/test_omission_recall.py` (11 tests).

Result on the 55 processed documents:

| Content | Extracted | Reached the patient | Recall |
|---|---|---|---|
| Medications (agent 3) | 307 | 307 | **100.0%** |
| Warning signs (agent 5) | 53 | 53 | **100.0%** |

**Scope, stated honestly in the report itself:** this measures only the leg we
own completely, content Agent 1 extracted that then failed to reach the
patient. The extraction record is the ground truth, so no annotation is
needed. The source-to-extraction leg needs his gold standard (item 3.5) and is
NOT covered by these numbers.

**How the first version was wrong, and why that is worth telling him.** The
initial implementation reported six dropped warning signs. All six were false
positives: plural mismatches ("fevers" vs "fever"), and one case where Agent 5
correctly rendered "edema" as "swelling in arms or legs" - a successful
plain-language translation scored as a safety omission. A metric that
penalises the product for doing its job measures the opposite of the goal.

The fix also made the check stricter where it counts: a **threshold number is
now pass/fail rather than one vote among several**, so a guide that says
"fever over 101" for a document that said 100.5 is caught. That is the more
dangerous failure, because substituted advice reads as correct to the patient
and is wrong for their case. `test_substituted_threshold_is_caught` locks it.

---

## Section 3 - Technical

### ✅ 3.1 PDF stack copyleft audit - already clean

Verified 25 Aug. `requirements.lock.txt` pins `pdfplumber==0.11.9` and
`pypdf==6.10.2`. `DEPENDENCIES.md` lists `pdfminer.six` (MIT), `pdfplumber`
(MIT), `pypdfium2` (BSD-3-Clause / Apache-2.0). **No PyMuPDF and no `fitz`
import anywhere in the tree.** His concern does not apply to us.

Answer this one concretely in the reply. It costs nothing and buys standing
for the items where we push back.

### ◑ 3.2 Post-hoc grounding verifier with hard failure

His point: no-fabrication is a prompt constraint, not an architectural
guarantee. Every clinical entity, dose, date and appointment in an output
should string- or entity-match the extraction record, failing hard otherwise.
That also makes the citation chips trustworthy.

**He predicted, from the architecture alone, the exact failure our own run
measured.** `evaluation/corpus_accuracy_report.md` (16 Aug): **47 of 55
outputs contain a number absent from the source document.**

We are ahead of him on diagnosis and behind on remedy. The report already
classifies the hits: 46 prompt-supplied clinical thresholds ("over 101 F"),
38 model-invented activity targets, and the Agent 4 prompt *requires* one
weekly goal, so the requirement manufactures the invention when the source
sets none. Medication names absent from source: **0**, so the Agent 1 contract
holds.

Verified 25 Aug: grounding logic exists in `extraction_agent.py` and the chat
service, with `test_extraction_grounding.py` and `test_chat_grounding.py`, but
there is **no post-hoc verifier gating agents 2-5 output**.

**Assessment: highest-value tractable technical item.** Deferred past the
26 Aug demo because a hard-failure gate is not something to introduce hours
before a live run.

### ⚑ 3.3 Stratified corpus across at least four source formats

**Right in principle; we should push back on scope.** Our 106 MTSamples
documents are all one stratum: dictated transcriptions. So our accuracy claim
generalises less than it appears to, and he is correct to say so.

The constraint he cannot see: we are at 55 of 106 processed, throttled by
Vertex **dynamic shared quota**, which has no per-project limit and therefore
**cannot be raised by request**. Four strata multiplies a problem we cannot
currently solve.

**Proposal: add one contrasting stratum** (a clean Epic-style after-visit
export) and report per-stratum honestly across two, rather than promise four
and deliver a partial run of each.

### ◻ 3.4 Prefer FHIR; treat PDF as fallback ⚑

Architecturally correct, out of scope for the remaining weeks. This rebuilds
the ingestion premise, and the program plan says October delivers a finished
artefact rather than the construction of a new one.

**Proposal:** acknowledge it as the right production direction, record it in
`INTEGRATION_READINESS.md` as the named next step, and do not attempt it this
cycle. That answer is more credible than a half-built FHIR path.

### ⚑ 3.5 Gold standard of 50-100 clinician-annotated documents

Correct methodology, and **it collides with his own milestone plan.** He asks
for 25 clinician-annotated documents by week 8. Task 4.2 has been blocked for
weeks on LOF assigning even 1-2 reviewers for 5-10 documents. He is asking for
several times that annotation effort, and clinician time is the scarcest
resource in this project.

**Raise directly with him, because he may be the one who can unblock it.** If
he can supply annotators this becomes feasible. If not, the honest deliverable
is a smaller gold set with stated confidence limits.

### ◻ 3.6 Report Agent 6 agreement with human teach-back

Fair and precise: Agent 6 is a language model grading a language model.

In our favour, we already treat it as advisory and non-fatal, and the AI
Review tab is framed as gaps to discuss with a care team rather than a
verdict. We are not making the claim he warns against.

The fix is cheap once tester data exists: correlate Agent 6 gap scores against
actual human quiz failures. **Blocked on the same testers as 2.1.**

### ◑ 3.7 Engineering hygiene

Mostly in place and worth claiming: Python dependencies locked
(`requirements.lock.txt`), partial-failure logging structured and deliberately
redesigned in August, and the **BAA path is live** (Vertex AI under BAA via
ADC; no API key has existed since 16 Aug). Stronger than he assumes.

**The real gap is pinned model versions.** `.env` deliberately leaves
`LLM_MODEL` unset to inherit the provider default, so Google can change the
model under us and our accuracy evidence silently expires. For a submission
whose central claim is measured accuracy, that is a genuine hole and a small
fix. Needs a documented re-evaluation trigger on version change.

### ⚑ 3.8 Keep the annotated corpus out of the repository - CONFLICT

**This contradicts a decision already made and documented. Do not silently
comply.**

Per `docs/deliverables/README.md`: the corpus was committed 14 Aug, after the
repository went private on 31 Jul, after all 106 documents were scanned for
SSNs, phone numbers, emails, MRNs and dates of birth with zero hits. The LOF
program rule permits clinical and eval data in a private repository.

His advice is more conservative than the written rule requires. He may know
something about IIT or LOF expectations the rule does not capture, or he may
be applying a sensible default without knowing the repo is private.

**Ask him which.** If he holds the line we comply, and note that removal means
rewriting history, not just deleting files.

---

## Section 4 - His milestone plan, weeks 7-13

**Timing problem to raise first: we are in week 8 now**, so his week 7 block is
already past due under his own schedule, and his plan does not map onto our
existing sprint structure. His Gate 3 at week 10 does align with Checkpoint 3
on 15 Sep, which is the useful anchor.

| Week | His deliverable | Our position |
|---|---|---|
| 7 | Stratified 50-doc corpus, annotation schema, license audit | License audit ✅ clean. Stratification contested, see 3.3 |
| 8 | Clinician-annotate 25 docs; precision/recall per stratum | ⚑ blocked on clinician availability, same bottleneck as 4.2. Most likely item to slip |
| 9 | Grounding verifier with hard failure; freeze physician-signed escalation template; convert Output 4 to template-filled | **Highest-value week in his plan.** Items 3.2 and 2.2 together |
| 10 (Gate 3) | All five outputs + grounded chat end to end **including failure paths**; evidence package | Well positioned: `rejected` status, `complete_with_warnings`, and media fallback tests already cover much of the failure-path demand |
| 11-13 | Teach-back study in 10-15 lay readers; CDS memo; rehearsed demo with backup recording | Recording runbook exists (`f861677`); the study is the tester blocker again |

---

## The three things that matter most

1. **His top clinical ask and our stalled Checkpoint 2 are the same blocker.**
   Testers gate 2.1, 3.6, task 3.5 prompt tuning, and Checkpoint 2 acceptance.
   One missing cohort wearing four hats.
2. **He independently predicted our measured failure** (3.2 vs the 47/55
   grounding result). Lead the reply with that: it shows the evaluation is
   honest enough to surface our own problems.
3. **The escalation template (2.2) is the item not to defer.** Unaddressed in
   code, highest-risk patient-facing output by our own rules.
