<!--
File: templates/escalation/hip_replacement.md
Owner: Likitha Shankar
Description: Hip Replacement-specific escalation criteria, layered on universal.md.
Used by: dischargeiq/utils/escalation_templates.py
Critical rules: UNSIGNED - inert until a physician signs the block at the end.
-->

# Hip Replacement - Escalation Tier Template

**Guideline reference:** [Pending reviewer confirmation - AAOS is the guideline named for hip replacement elsewhere in this project]

Adds to `universal.md`. The universal criteria still apply in full.

## CALL 911 IMMEDIATELY
- Sudden chest pain with shortness of breath
- The leg is cold, pale, or has no feeling

## GO TO THE ER TODAY
- Calf pain or swelling in one leg
- The hip pops out of place, or the leg looks shorter or turned
- The wound opens, or drains pus
- A fall onto the new hip

## CALL YOUR DOCTOR
- Bruising that is slowly fading
- Stiffness that improves as you move
- Questions about how far to walk

## Reviewer notes

- Sudden chest pain with breathlessness is placed in Tier 1 as a possible
  clot after joint surgery. Universal criteria already cover chest pain, so
  this is a diagnosis-specific reinforcement. **Reviewer: confirm.**
- Hip precaution angles (for example a 90 degree bend limit) are deliberately
  NOT included. The 25 Aug corpus run found the system inventing "do not bend
  more than 90 degrees" for documents that set no such limit, and protocols
  differ between surgeons. **Reviewer: confirm precautions must come from the
  patient own document, or supply a default.**
- Everything in this file is a PROPOSED addition. Unlike `universal.md`,
  these criteria are not a restructuring of shipped prompt behaviour, because
  `agent5_system_prompt.txt` carries no per-diagnosis tier lists. **Reviewer:
  accept, reject or correct each line.**
- The reviewer decides tier placement, not just wording. A criterion in the
  wrong tier is more dangerous than a criterion phrased awkwardly.

## Clinical sign-off

**Reviewed by:** [Pending - Dr. Liebovitz / designated reviewer]
**Date:** [Pending]
**Status:** Awaiting faculty review
**Changes made based on review:** [To be completed after faculty feedback]
