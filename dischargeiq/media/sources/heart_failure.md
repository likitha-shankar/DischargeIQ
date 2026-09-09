# NotebookLM source - Heart Failure explainer

<!--
Task 4.2 source document. Paste this whole file into a NotebookLM notebook as
the ONLY source, then generate the Audio Overview (and optionally Video).
Bulleting + phonetic hints are the pacing/pronunciation levers - NotebookLM
reads structure, so short bullets = calm pacing, phonetic hints = correct
drug-name pronunciation. Clinical text is taken verbatim from the
clinician-reviewed template templates/heart_failure.md - do NOT add facts here.
-->

## How to narrate this
- Audience: a patient who just got home from the hospital.
- Plain language, short sentences, sixth-grade level. No medical jargon.
- Do NOT give any medication-change advice. Never say "stop" or "consider stopping" a drug.
- Calm, unhurried pace. Pause between bullets.

## Pronunciation hints (say it this way)
- diuresis -> "die-yoo-REE-sis" (better: just say "medicine to remove extra fluid")
- Furosemide -> "fyoor-OH-seh-mide"
- Lisinopril -> "lie-SIN-oh-pril"
- Metoprolol -> "meh-TOH-proh-lol"

## What to explain (in this order)
- Your heart was not pumping blood the way it should.
- This caused fluid to build up in your lungs and legs.
- That is why you felt short of breath and your legs were swollen.
- In the hospital, doctors gave you medicine through a tube in your arm to remove the extra fluid.
- Your heart still needs help pumping blood.
- The pills you are going home with will do that job.

## The one habit that matters most
- Weigh yourself every morning, before you eat.
- Write the number down every day.
- Your own discharge papers tell you how much weight gain to call about.
- The app shows that number on your Warning Signs page. Follow that one.
- If you gain weight quickly and you are not sure, call your doctor.

<!--
NO NUMBER HERE, DELIBERATELY. This file said "more than two pounds in one
day, call your doctor". That is the ACC/AHA 2022 threshold and it is correct
as general guidance - templates/heart_failure.md cites it and keeps it.

But this audio is GENERIC. Every heart-failure patient hears the same file,
and it plays inside an app that is simultaneously showing them the threshold
from their OWN discharge summary. On the demo document that is 3 lb, and the
action is GO TO THE ER TODAY rather than "call your doctor". So a patient
heard a lower number attached to a less urgent action, and read a higher
number attached to a more urgent one, from one product.

That is Dr Liebovitz's central point arriving through the audio path: a
general clinical threshold presented as if it applied to this patient. The
post-generation threshold guard strips these from agent text, and cannot
reach here, because generic audio has no source document to check against.

The fix is not to change the number - picking 3 lb would be adopting one
patient's threshold as everyone's, which is worse. It is to stop this file
competing with the patient's own paperwork and point at it instead.
-->
