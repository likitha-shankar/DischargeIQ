# Physician oversight for AI-generated warnings: two options

**Action item from the LOF review, 26 Aug 2026 (01:03:44):** *investigate
practical physician oversight for AI-generated warnings and propose 1-2
implementation options.* The constraint stated in the meeting was explicit:
find a trust mechanism **without overburdening clinicians** (01:02:34).

## The problem, stated precisely

The three-tier escalation guide tells a patient when to call 911, when to go
to the ER today, and when to call their doctor. It is the highest-risk output
in the product, and until recently no clinician stood behind any of it.

The meeting characterised this as *"roughly 50% of warning signs are
fabricated"*. Our measurement says something different and more specific, and
the distinction changes what oversight is needed:

| Measured | Result |
|---|---|
| Warning signs extracted that reached the patient | **53/53 (100%)** |
| Medication names in output absent from source | **0** |
| Documents carrying a NUMBER absent from source | **was 80%, now 0%** |

Warning-sign **recall** was never the problem. The problem was **numeric
thresholds** the system supplied on its own: fever limits, and in one case
`"Fast heart rate: Call 911 if it is over 100."` A resting heart rate over 100
is common and usually harmless. That instruction appeared in no source
document, sat in the CALL 911 tier, and would have sent people to an emergency
room for nothing.

## Why this needs a clinician and not better engineering

We tried to solve it in software twice, and the second attempt is the
argument for this whole document.

1. **Attempt one:** forbid inventing thresholds, listing the bad values
   inline. The model then produced `"Fever above 100.4 degrees F"` on a
   **neonatal** document that mentioned no fever at all. Enumerating the
   forbidden numbers primed them.
2. **Attempt two:** permit exactly one default, 101 F. On review this was
   clinically wrong: for an infant **100.4 F is the correct threshold** and
   101 F is not. Had the model obeyed the instruction exactly, it would have
   told a newborn's parent to wait longer than they should.

**The model's number was better than the rule we wrote for it.** That is the
finding. A safe threshold depends on age and condition, and no prompt author
without clinical training should be choosing one.

**Current behaviour, shipped:** Agent 5 now supplies **no** threshold when the
document gives none, and describes the observable sign instead - *"a fever
that will not come down"*. A threshold the document DOES state is reproduced
verbatim. That is safe. It is also incomplete, because a patient with no
threshold in their paperwork gets less guidance than they could.

Closing that gap is a clinical decision. Everything else is already built.

---

# Option 1 (recommended): sign the templates once, not per patient

**What already exists.** `templates/escalation/` holds six criteria files -
one universal, one per target diagnosis. `escalation_templates.py` loads them,
parses a sign-off block, and `verify_guide()` reports any Tier 1 criterion a
generated guide demoted or dropped. Fifteen tests cover it.

**A template is inert until signed.** It governs output only when its sign-off
names a real reviewer and a real date. All six ship unsigned, so patient-facing
behaviour today is unchanged. A drafted-in-repo template treated as
authoritative would be strictly worse than generated text: identical clinical
risk, now wearing a "clinician-reviewed" label.

**The clinician burden, bounded and one-time.**

| | |
|---|---|
| What they review | 6 markdown files, 3 tiers each, ~40 criteria total |
| Estimated time | **60-90 minutes, once** |
| Repeat cost | Zero per patient. Re-review only when criteria change |
| What they sign | Two fields: `Reviewed by` and `Date` |

**Why it is not per-discharge review.** Per-patient sign-off is the obvious
design and the wrong one: it scales with volume, it puts a clinician in the
critical path of every upload, and it is exactly the overburdening the meeting
warned against. Signing the CRITERIA once transfers authority to every future
document that matches the diagnosis.

**What signing unlocks technically.**

- The signed thresholds become the default when a document states none, so
  patients stop losing guidance their paperwork omitted.
- `verify_guide()` starts enforcing: any generated guide that demotes a
  clinician's Tier 1 criterion is reported.
- Three questions currently blank get answered - the fever threshold and
  whether it varies by age, hip precaution angles, and diabetes glucose
  targets. All three are omitted today precisely because we could not pick
  them safely.

**Open question for the reviewer, and it is the important one:** is a single
universal fever threshold safe across ages, or must it vary? Our evidence says
a single number is wrong. `templates/escalation/universal.md` records the full
episode in its reviewer notes.

---

# Option 2 (complementary, buildable now): separate what the document said from what medicine says

Option 1 answers *who authorises the guidance*. This answers *how the patient
knows where it came from*, and it can ship without waiting for a signature.

**The real defect in the original finding** was never that general clinical
guidance is useless. It is that guidance was **attributed to the patient's own
discharge paperwork** when their doctor never wrote it. A fever threshold
presented as "your doctor says" carries authority it has not earned.

**The change:** render two visually distinct classes in the warning-signs tab.

- **From your discharge summary** - extracted, with the existing citation chip
  linking to the source page.
- **General guidance** - clinician-authored default, labelled as such, with
  the reviewer's name once a template is signed.

**Why this is worth doing regardless of Option 1:**

- It is honest. The patient can tell which instructions came from their own
  care team.
- It degrades well. Unsigned, the general section can be suppressed entirely -
  which is today's behaviour, now visible rather than implicit.
- It gives the clinician something concrete to sign: they are authorising a
  clearly demarcated block, not silently blessing generated prose.
- The citation infrastructure already exists; this reuses it.

**Cost:** a rendering change on both surfaces plus a field on the escalation
output. No clinician time.

---

## What we are NOT proposing, and why

**Per-discharge clinician review.** Scales with patient volume, puts a human in
the critical path of every upload, and is the overburdening the meeting
explicitly warned against.

**A patient support forum.** Raised in the meeting (01:02:34) as an
alternative trust mechanism. It answers a different question - what happens
after a patient is confused - and does not validate the warning before it is
shown. Worth considering separately; it is not oversight.

**Shipping unsigned defaults.** We can build the mechanism, and we have. We
cannot supply the clinical values, and the two failed attempts above are why.

## Recommendation

Do both. **Option 2 now**, because it is honest, cheap, and needs nobody's
calendar. **Option 1 as soon as a reviewer can give 90 minutes**, because it is
the only thing that closes the gap for patients whose paperwork states no
threshold.

Ask Dr. Liebovitz for one 90-minute session against
`templates/escalation/*.md`. Re-run
`python scripts/escalation_template_status.py` afterwards; it currently reports
0 of 6 signed and states plainly that none of them govern output.
