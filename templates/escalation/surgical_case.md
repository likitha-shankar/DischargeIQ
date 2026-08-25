<!--
File: templates/escalation/surgical_case.md
Owner: Likitha Shankar
Description: Surgical Case-specific escalation criteria, layered on universal.md.
Used by: dischargeiq/utils/escalation_templates.py
Critical rules: UNSIGNED - inert until a physician signs the block at the end.
-->

# Surgical Case - Escalation Tier Template

**Guideline reference:** [Pending reviewer confirmation - ACC/ACS perioperative is the guideline named for surgical cases elsewhere in this project]

Adds to `universal.md`. The universal criteria still apply in full.

## CALL 911 IMMEDIATELY
- The wound opens and organs or tissue show
- Bleeding through the dressing that will not stop
- Sudden chest pain or trouble breathing

## GO TO THE ER TODAY
- The wound is red, hot, or draining pus
- Fever with shaking chills
- Belly pain that keeps getting worse
- Cannot pass urine for 8 hours

## CALL YOUR DOCTOR
- Itching around the healing wound
- Mild swelling near the cut that is going down
- Questions about showering or changing the dressing

## Reviewer notes

- The wound-opening criterion is placed in Tier 1 rather than Tier 2 because
  it is time-critical and unambiguous. **Reviewer: confirm.**
- Cannot pass urine for 8 hours is proposed for Tier 2 as post-operative
  retention. **Reviewer: confirm the interval.**
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
