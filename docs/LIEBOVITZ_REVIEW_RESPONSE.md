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

### ◑ 2.2 Anchor escalation tiers to a physician-signed template - MECHANISM BUILT

His point: the three-tier guide is the highest-risk output because it gives
triage advice with no clinician in the loop. Make the tiers template-filled
from clinician-authored criteria, not generated.

**Right. It was entirely unaddressed when the review arrived:**
`escalation_agent.py` contained **no reference to any template**. The markdown files in
`dischargeiq/templates/` are diagnosis explainers and Agent 5 does not read
them. Agent 5 output is fully generated text.

Our own `CLAUDE.md` hard rule 3 already calls Agent 5 safety-critical and
requires every output to be read manually. He is saying manual review does not
scale and the guarantee belongs in the architecture. Converting Output 4 from
generated to template-filled is a real build, not a prompt edit.

**Assessment: highest-liability item on the list.** Hardest thing to defend to
a reviewer or a regulator as currently built.

**Built 25 Aug 2026. The mechanism is done; the signatures are not, and cannot
be done inside this repository.**

`templates/escalation/` now holds six templates: `universal.md` plus one per
target diagnosis. `dischargeiq/utils/escalation_templates.py` loads them,
parses the sign-off block, and `verify_guide()` reports any Tier 1 criterion a
generated guide demoted or dropped. 15 tests in
`dischargeiq/tests/test_escalation_templates.py`.

**The design decision that matters: an unsigned template is inert.** A
template drafted in-repo and treated as authoritative would be strictly worse
than generated text - identical clinical risk, now wearing a
"clinician-reviewed" label. So a template governs output only when its
sign-off names a real reviewer AND a real date; `[Pending - ...]` parses as
unsigned, which is the placeholder the existing diagnosis templates already
use. All six ship unsigned, so **patient-facing behaviour is unchanged today**.
It changes on the day a physician signs, not the day the files landed.

`test_no_shipped_template_is_signed_yet` fails the moment one is signed. That
is deliberate: it forces a human to notice that triage advice has started
being governed by a template rather than it happening quietly.

**Provenance, which the reviewer should be told plainly.** Every criterion in
`universal.md` was lifted from the tier lists already in
`agent5_system_prompt.txt`, so he is reviewing what the system does today, not
a fresh proposal. The five per-diagnosis files ARE new proposals, because the
prompt carries no per-diagnosis tiers, and each says so in its reviewer notes.

Three questions were deliberately left for him rather than answered in a
prompt file, each tied to a real finding:

- **The fever threshold. This is now the most important question in the
  document.** The prompt no longer supplies any number, because two attempts to
  pick one both failed: first the model invented 100, 100.4, 102.2, 103 and 39
  for documents stating none, then a rule permitting only 101 F would have told
  a newborn's parent to wait for 101 when 100.4 is the correct neonatal
  threshold. Agent 5 now says "a fever that will not come down" and supplies no
  number at all. **That is safe but incomplete, and only a clinician can
  complete it.** See the full episode in the reviewer notes of `universal.md`.
- **Hip precaution angles.** Omitted deliberately: the same run found the
  system inventing "do not bend more than 90 degrees" for documents setting no
  limit, and protocols differ between surgeons.
- **Diabetes glucose numbers.** Omitted deliberately, for the same reason -
  targets are patient-specific.

**Remaining work:** send `templates/escalation/*.md` to him, have him correct
the criteria and fill in the sign-off, then re-run
`scripts/escalation_template_status.py`. It currently reports 0 of 6 signed and
states plainly that none of them govern output.

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

**Assessment: highest-value tractable technical item.**

**Verifier built 25 Aug 2026, deliberately report-only.**
`dischargeiq/utils/grounding.py` plus 12 tests. It is NOT wired in as a hard
failure, and the reason is a measurement: across 59 corpus outputs a hard gate
would block **50 of them, 85%**, or 64% counting only invented values. Wiring
that in would have failed almost every document and taught everyone to route
around the gate. `scripts/grounding_gate_readiness.py` makes that number
repeatable and prints a verdict rather than a bare percentage.

**The measurement found the cause, which was the useful part.** agent4
accounted for 48 of 55 invented values, and the single value 15 appeared 26
times. The Agent 4 prompt REQUIRED one specific goal per week while the
grounding rule forbade unsupported content, so when a document set no goal the
model had to break one of them. Worse, the prompt's own worked example read
"Your goal this week is to walk for 15 minutes without stopping" - it was
demonstrating the exact number it then produced.

**Both prompts fixed 25 Aug.** Agent 4's goal is now conditional and must be
built from a restriction the document states, with inventing a number for one
forbidden outright; the example now shows a week with no goal at all, because
an absent goal had to be shown as valid output. Agent 5 gained a NUMBER RULE
after the run surfaced something worse than a grounding miss:

    mtsamples_057, Tier 1:  "Fast heart rate: Call 911 if it is over 100."

A resting heart rate over 100 is common and usually harmless, that number is in
no source document, and it is in the CALL 911 tier. Two others: mtsamples_018
invented "over 102.2 F (39 C)", and mtsamples_048 used both 101 and 103 in one
guide. Document thresholds now always win verbatim; absent one, 101 F is the
only permitted fever number; numbers on any other vital sign are forbidden
unless the document states them.

**Also corrected: a defect in our own verifier.** Its excuse list treated
100.4, 101.5 and 102 as prompt-supplied when no prompt contains them, so ten
genuinely invented thresholds were being hidden. Fixing it made the figures
worse - invented 45 to 55, block rate excluding thresholds 56% to 64% - which
is the correct direction for an honest instrument, and it exposed that agent4
emits 100.4 eight times too.

### VERIFIED 25 Aug 2026, and it took three attempts

Outputs were regenerated and measured. **Same 10 documents, same measuring
code, only the prompts differ:**

| | Before | After |
|---|---|---|
| Documents carrying invented values | **8 of 10 (80%)** | **0 of 10 (0%)** |
| agent4 | 8 | 0 |
| agent5 | 4 | 0 |
| agent2 | 1 | 0 |

**Both directions of the rule are verified, not just the convenient one.** A
fix that suppressed genuine thresholds along with invented ones would be worse
than the original bug, so the two documents whose source text DOES state a
threshold were regenerated separately:

- `mtsamples_054` source says "fever greater than 100.5" -> guide says
  "Fever greater than 100.5"
- `mtsamples_064` source says "temperature greater than 101.5" -> guide says
  "Temperature greater than 101.5"

Both now reproduce the document's own wording more exactly than the old prompt,
which rendered them as "over".

**Nothing was hollowed out to reach zero.** Regenerated outputs keep three
tiers and 10 to 30 bullets, and readability improved rather than degraded:
`mtsamples_003` came back at FK 4.07 with 30 bullets; `mtsamples_001` gained a
bullet and moved from FK 5.3 to 4.52.

### Three attempts, because the same bug was in three places

Worth telling him plainly, because the pattern is the finding:

1. **Agent 4 goals.** The prompt required "one specific action or goal for
   that week" while the grounding rule forbade unsupported content. Its own
   worked example read "walk for 15 minutes without stopping" - and
   `agent4:15` was the most common invented value in the corpus, 26
   occurrences. The example was teaching the number it then produced.
2. **Agent 5 tiers.** A rule was added saying "supply no threshold", but the
   tier list still contained "Fever above 101 degrees F" and so did the output
   example. The model followed the example. `mtsamples_013` and `_014` both
   emitted 101 for documents mentioning no fever at all, AFTER the rule landed.
3. **Agent 4 again.** Its third required topic is "what requires calling the
   doctor", so it writes escalation-style bullets too. `mtsamples_003` produced
   "Call your doctor if you have a fever over 100.4 F (38 C)" from a document
   that said nothing of the kind.

The general lesson, which applies beyond these three: **a rule that says "do
not" and an example that shows "how" will lose to the example.** Every worked
example in a prompt is training data.

### One failure worth showing him, because it was mine

The first Agent 5 attempt enumerated the forbidden numbers inline: "not 100,
not 100.4, not 102.2, not 103". Regenerating produced, on a NEONATAL document
mentioning no fever at all:

    - Baby has a fever: Fever above 100.4 degrees F needs checking.

Two things went wrong. The enumeration primed the very values it forbade. And
the rule permitted only 101 F, which for an infant is clinically wrong -
100.4 F is the correct neonatal threshold. **Had the model obeyed the
instruction exactly, it would have told a newborn's parent to wait for 101.**
The model's number was better than the rule it was given.

That is the strongest argument in this whole document for item 2.2. A fever
threshold is not a value a prompt author can pick, and this is what it looks
like when one tries. See `templates/escalation/universal.md`, where he is asked
to set the thresholds and say whether they vary by age.

### Methodology note, recorded so the numbers can be trusted

The saved pre-fix baseline can NOT be compared against post-fix figures,
because the measuring instrument changed in between: the excuse list that
suppressed `101` was emptied. Running that comparison shows agent5 going 6 to
32 and reads as catastrophic regression when it is only reclassification of
old-prompt outputs. Every figure above holds the instrument constant and varies
only the prompt.

A comparison across an instrument change is not a measurement. Outputs now
stamp `prompt_versions` so before and after can be told apart from the file
itself rather than by reading modification times.

**Still outstanding:** a full-corpus regeneration is running. Until it
finishes, corpus-wide gate figures mix old-prompt and new-prompt outputs and
mean nothing. The 10-document paired result above is the verified claim.

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

### ◑ 3.7 Engineering hygiene - provenance DONE, pinning is a decision

Mostly in place and worth claiming: Python dependencies locked
(`requirements.lock.txt`), partial-failure logging structured and deliberately
redesigned in August, and the **BAA path is live** (Vertex AI under BAA via
ADC; no API key has existed since 16 Aug). Stronger than he assumes.

**The real gap was pinned model versions, and it was worse than it looked.**
`.env` leaves `LLM_MODEL` unset to inherit the provider default, and
`gemini-2.5-flash-lite` is a **floating alias** Google can repoint without
notice. Worse, nothing recorded which model produced any evidence: verified
25 Aug, `_review_meta` held document and timing but no provider or model, and
the accuracy report never stated what it measured. The report going to Gate 3
could not vouch for itself.

**Fixed 25 Aug 2026.** `run_corpus_for_review.py` now stamps `llm_provider`
and `llm_model` into every output, and the accuracy report opens with section
0, "What produced these numbers". It also refuses to look clean when it
cannot: pre-stamp outputs show as `unrecorded` with a warning, and a run
spanning more than one configuration is called out as not a single
measurement. **All 59 existing outputs are `unrecorded` and must be re-run
before the report is cited as gate evidence.**

The re-evaluation trigger he asked for is documented in
`docs/MODEL_VERSIONING.md`: re-run on a provider change, a model or alias
change, any agent prompt change, or an extraction-schema change. Prompt edits
are in that list deliberately - the 47/55 grounding finding traces to a prompt
requirement, not to the model.

**Left as a decision, not made unilaterally:** pinning `LLM_MODEL` for
evaluation runs while production stays on the provider default. That
deliberately diverges evaluation from production, which contradicts the 16 Aug
decision to keep `.env` matching Cloud Run - a decision taken because a
Vertex-only model-name bug survived exactly that divergence.

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
3. **The escalation template (2.2) is the item not to defer, and we now have
   evidence rather than agreement.** The mechanism is built and inert until
   signed. What changed on 25 Aug is that we tried to pick a fever threshold
   ourselves and got it wrong in both directions: first by letting the model
   invent one, then by writing a rule that would have told a newborn's parent
   to wait for 101 F. A threshold is not a value a prompt author can choose.
   That question is now the first thing in
   `templates/escalation/universal.md`.
