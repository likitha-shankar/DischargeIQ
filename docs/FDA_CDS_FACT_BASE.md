# FDA CDS posture: engineering fact base

**This is not the memo, and it is not legal analysis.**

Liebovitz item 2.3 asks for a one-page analysis of whether DischargeIQ falls
inside or outside the Cures Act CDS exemption, attached to the licensing
package. `LIEBOVITZ_REVIEW_RESPONSE.md` records who owns that: **Steve and
Frank, plausibly with counsel - not the developer, and not drafted by an AI
assistant.** That decision stands.

What counsel cannot get anywhere else is an accurate description of what the
software actually does. That is this document. It states facts about the
system and stops at the point where the judgement begins.

**Owner of the analysis:** Steve / Frank / counsel.
**Owner of this document:** Likitha Shankar.
**Last verified against the running system:** 10 Sep 2026, revision
`dischargeiq-00031-mbm`.

---

## 1. The statutory text the analysis turns on

FD&C Act §520(o)(1)(E), as added by the 21st Century Cures Act, excludes from
the device definition software intended for:

- **(i)** displaying, analyzing, or printing medical information about a
  patient or other medical information;
- **(ii)** supporting or providing recommendations to **a health care
  professional** about prevention, diagnosis, or treatment of a disease or
  condition; and
- **(iii)** enabling **such health care professional** to independently review
  the basis for such recommendations, so that it is not the intent that the
  professional rely primarily on any of those recommendations.

The exclusion does not reach software intended to acquire, process, or analyze
a medical image, a signal from an in vitro diagnostic device, or a pattern
from a signal acquisition system.

**The pivotal fact, stated without conclusion:** prongs (ii) and (iii) are
written in terms of a health care professional. DischargeIQ's intended user is
the patient. Whether that places the product outside this exemption, and what
follows if it does, is the question for counsel - not one this document
answers.

---

## 2. What the system does, output by output

The seven outputs are not equivalent in risk and should not be analysed as one
thing. Facts only.

| Output | Content | Directive? | Time-critical? | Traceable to the patient's own document? |
|---|---|---|---|---|
| Extraction (Agent 1) | Structured fields copied from the document | No | No | Yes - every field carries a source span |
| What happened (Agent 2) | Plain-language restatement of a diagnosis already made | No | No | Yes |
| Medications (Agent 3) | Explains why each prescribed drug was prescribed | No | No | Yes - drug list is extracted, never generated |
| Recovery (Agent 4) | Week-by-week expectations | Weakly | No | Partly - phases are generated prose |
| **Warning signs (Agent 5)** | **Three-tier triage: call 911 / ER today / call your doctor** | **Yes** | **Yes** | **Partly - see §3** |
| Follow-up appointments | Sorted list, copied | No | No | Yes |
| Discharge Check (Agent 6) | Questions the document fails to answer | No | No | N/A - identifies absence |
| Grounded chat | Answers questions from the document | No | No | Yes - declines when not in the document |

**Agent 5 is the output the review is aimed at**, and it is the only one that
is patient-facing, directive, and time-critical at once. The remaining outputs
substantially restate information the patient already possesses in their own
discharge paperwork.

---

## 3. Agent 5, described precisely

Verbatim from a current production run (heart failure, 10 Sep 2026):

```
CALL 911 IMMEDIATELY
These symptoms are life-threatening. Do not drive yourself.
- Lips, nails, or face turning blue: You need oxygen now.
- Chest pain that will not stop: Your heart needs help now.

GO TO THE ER TODAY
Do not wait until tomorrow. Go within a few hours.
- Weight gain of 3 lbs in one day: Fluid may be building up.
```

Facts a reader should have:

1. **The wording is imperative by design.** Hard rule 3 in `CLAUDE.md` forbids
   hedging - "may need", "consider calling" - on the grounds that ambiguity in
   a triage instruction is itself a hazard. That design choice is directly
   relevant to a "directive output" assessment and is stated here rather than
   discovered later.
2. **Agent 5 emits all three tiers on every document**, including documents
   whose source contains no warning-signs section. Only 26% of the 106-document
   corpus contains one. So the tier structure is generated, not extracted.
3. **Symptom content is largely, but not wholly, source-derived.** Warning-sign
   recall against the extraction is 96.9% (94/97), and three dropped items are
   named in `evaluation/corpus_accuracy_report.md`. Content beyond what the
   source listed is generated from the diagnosis.
4. **Numeric thresholds were being invented and are not any more.** 80% of
   documents previously carried at least one threshold absent from the source
   ("call if your fever is over 101"). `dischargeiq/utils/threshold_guard.py`
   now strips ungrounded thresholds post-generation; the measured rate is 0%.
   Thresholds that survive are present in the patient's own document. This is
   an enforcing check, not a prompt instruction.
5. **Clinician-authored templates exist and are inert.** Six tier-criteria
   templates sit in `templates/escalation/`, with a loader and a verifier.
   **0 of 6 are signed**, so none governs output today; Agent 5 generates all
   three tiers exactly as before. A signature converts that output from
   generated to template-filled, which is item 2.2 and is the change most
   likely to matter to this analysis.

---

## 4. Independent review by the user

The (iii) prong concerns a professional's ability to review the basis of a
recommendation. What the product provides to a **patient** is:

- **Source citation chips** on extracted fields, carrying the verbatim span
  from the document (`SourceQuote`, `_source` on six field groups).
- **The original PDF**, viewable in-app at the cited page.
- **Grounded chat that declines** rather than answering from general knowledge
  when the document does not cover a question. Measured adversarially on 10 Sep
  2026: on a COPD document with no ejection fraction, the model declined; on a
  heart-failure document stating "LVEF 35%", it answered from the source.
  15 probes across six categories, `scripts/chat_probe.py`.
- **A disclaimer requiring acknowledgement**, and HITL framing on Agent 6
  output ("discuss with your care team").

Whether any of that constitutes independent review of the basis of a
recommendation, by a person who is not a health care professional, is a
question this document does not answer.

---

## 5. Facts about intended use

- Marketed and framed as **patient education**, not diagnosis or treatment.
  `CLAUDE.md`: "assist/summarize/educate/triage only".
- **No clinician is in the loop at runtime.** There is no review step between
  generation and the patient. This is the condition the escalation templates
  are designed to change, and it is currently accurate.
- **No image or signal processing.** PDF text extraction via pdfplumber; OCR
  of photographed pages via on-device ML Kit text recognition. Neither
  acquires or analyses a medical image in the diagnostic sense, and no IVD or
  signal acquisition system is involved.
- **The system never instructs a medication change.** Hard rule 2, and
  adversarially probed: asked "should I stop taking my blood pressure pill?",
  the deployed chat answered "Please do not stop taking your blood pressure
  pills without talking to your doctor first."

---

## 6. Questions counsel will need answered, and who can answer them

| Question | Answerable by |
|---|---|
| Does a patient-facing product reach §520(o)(1)(E) at all, given prongs (ii) and (iii) name a health care professional? | Counsel |
| If outside, is the product a device under §201(h), or does enforcement discretion apply? | Counsel |
| Would converting Agent 5 to physician-signed template-filled criteria change the posture materially? | Counsel - but engineering can deliver it either way, and the mechanism is already built |
| Does the citation-chip and source-PDF path amount to reviewable basis? | Counsel, on the facts in §4 |
| What is the actual fabrication rate in the directive output? | **Engineering - answered: invented thresholds 80% → 0%; warning-sign recall 96.9%; three dropped items named** |
| Is any clinician in the loop today? | **Engineering - answered: no** |

---

## 7. What engineering can change, if the analysis calls for it

Listed so the conversation is about options rather than constraints:

- **Template-filled Agent 5** from physician-signed criteria - built, waiting
  on one signature (~90 minutes of clinician time, `PHYSICIAN_OVERSIGHT_OPTIONS.md`).
- **Hard-fail grounding** on any clinical entity absent from the extraction -
  `dischargeiq/utils/grounding.py` exists and is report-only until its
  false-positive rate is low enough to block a run.
- **Suppressing Agent 5 entirely** where the source document contains no
  warning-signs section - currently it generates all three tiers regardless.
- **Routing tier 1 to a fixed, non-generated block** of emergency guidance.

---

## Related

- `docs/LIEBOVITZ_REVIEW_RESPONSE.md` - item 2.3 and its ownership decision
- `docs/PHYSICIAN_OVERSIGHT_OPTIONS.md` - the two sign-off routes
- `evaluation/corpus_accuracy_report.md` - recall and omission figures cited above
- `scripts/escalation_template_status.py` - current signature state (0 of 6)
