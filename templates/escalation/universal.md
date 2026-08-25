<!--
File: templates/escalation/universal.md
Owner: Likitha Shankar
Description: Diagnosis-independent escalation criteria. Applies to every
  patient regardless of primary diagnosis; per-diagnosis templates add to it
  rather than replace it.
Used by: dischargeiq/utils/escalation_templates.py
Critical rules: UNSIGNED - inert until a physician signs the block at the end.
  Criteria restructured verbatim from agent5_system_prompt.txt, not authored here.
-->

# Universal - Escalation Tier Template

**Guideline reference:** [Pending reviewer confirmation - criteria currently
derive from agent5_system_prompt.txt rather than a cited guideline]

These criteria apply to every patient whatever their diagnosis. A
diagnosis-specific template adds to this list; it never removes from it.

## CALL 911 IMMEDIATELY
- Cannot breathe, gasping, or breathing very fast
- Chest pain or pressure that does not go away
- Face drooping, arm weakness, or trouble speaking
- Sudden confusion that comes on fast
- Bleeding that will not stop with pressure
- Passing out, or cannot be woken up
- Crushing chest pain with cold sweat or pain down the arm
- Throat or face swelling, or trouble swallowing
- Seizure

## GO TO THE ER TODAY
- Fever above 101 degrees that will not come down
- Wound looks infected: red streaks, pus, or warm to touch
- Severe pain that medicine does not help
- Swelling in one leg, especially with pain
- Cannot keep fluids down for 12 hours
- New confusion that is getting worse
- A fall with an injury

## CALL YOUR DOCTOR
- Mild pain that is slowly getting better
- Questions about a medicine or a dose
- Wound healing slowly with no signs of infection
- Mild swelling without pain
- Feeling sick to your stomach without throwing up
- Tiredness that is improving
- Minor redness that is not spreading

## Reviewer notes

- Every criterion here was taken from the tier lists already in
  `agent5_system_prompt.txt`. Nothing was authored for this file. The reviewer
  is therefore reviewing what the system does today, not a new proposal.
- The prompt states the fever threshold as "above 101 degrees F (38.5 C)".
  Rendered here without the Celsius conversion to keep the reading level down.
  **Reviewer: confirm 101 F is the right universal threshold, or set the right
  one.** The 25 Aug corpus run found Agent 5 emitting 100, 102.2, 103 and 39 as
  thresholds that appear in no source document, so this number is doing real
  work and is currently unowned.
- The prompt also instructs the agent to promote a universally
  life-threatening symptom to Tier 1 even when the discharge document omits it.
  **Reviewer: confirm that behaviour is wanted.** It is a deliberate departure
  from "only say what the document says" and is justified on safety grounds.
- Tier 3 explicitly tells patients NOT to go to the ER for these. Reviewer to
  confirm that instruction is acceptable without clinician contact.

## Clinical sign-off

**Reviewed by:** [Pending - Dr. Liebovitz / designated reviewer]
**Date:** [Pending]
**Status:** Awaiting faculty review
**Changes made based on review:** [To be completed after faculty feedback]
