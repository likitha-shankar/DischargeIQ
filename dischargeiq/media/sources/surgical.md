# NotebookLM source - Surgical / Laparoscopic explainer

<!--
Task 4.2 source document. Paste this whole file into NotebookLM as the ONLY
source, generate the Audio Overview (and optionally Video). Clinical text is
verbatim from templates/surgical_case.md - do NOT add facts. Filename uses the
router label "surgical" (matches _ALLOWED_TYPES in api/routes/media.py).
-->

## How to narrate this
- Audience: a patient who just got home from the hospital.
- Plain language, short sentences, sixth-grade level. No medical jargon.
- Do NOT give medication-change advice.
- Calm, unhurried pace. Pause between bullets.

## Pronunciation hints (say it this way)
- laparoscopic -> "lap-uh-roh-SKOP-ik" (better: just say "small-cut surgery")

## What to explain (in this order)
- Your doctor made small cuts in your belly to do the surgery.
- A tiny camera and small tools went through the cuts.
- Small cuts hurt less and heal faster than one big cut.
- You may feel some pain in your shoulder or chest for a day or two.
- This comes from the gas used in the surgery. It will go away on its own.

## What to do at home
- Your discharge papers say how much you can safely lift, and for how long.
- The app shows that on your Recovery page. Follow that one.
- If your papers do not say, ask your surgeon before you lift anything heavy.

<!--
Was "do not lift more than ten pounds for two to four weeks" - the ACC/ACS
figure, correct as general guidance and kept in templates/surgical_case.md.
Removed here for the same reason as the heart-failure weight rule: a generic
explainer must not hand a patient a number that competes with the one in
their own summary. A lifting limit differs between surgeons and procedures.
-->
- Do not drive while you take pain pills.
- Start walking the day you get home. Do a little more each day.

## What to expect
- Your summary says when you should start feeling better.
- Full healing takes two to four weeks.

<!--
Collective phrasing removed 10 Sep 2026 (Frank Naeymi-Rad): speak
about this patient, not about people in general.

Was: "Most people feel better in one to two weeks."

This is a GENERAL explainer with no patient document behind it, so
there is no "your plan" to attribute a timeline to - and a claim
about a population, heard by someone whose recovery is slower, tells
them they are behind. The fix is the one heart_failure.md already
records for its fever threshold: stop competing with the listener's
own paperwork and point at it instead.
-->
