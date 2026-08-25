<!--
File: templates/escalation/copd.md
Owner: Likitha Shankar
Description: COPD-specific escalation criteria, layered on universal.md.
Used by: dischargeiq/utils/escalation_templates.py
Critical rules: UNSIGNED - inert until a physician signs the block at the end.
-->

# COPD - Escalation Tier Template

**Guideline reference:** [Pending reviewer confirmation - GOLD 2024 is the guideline named for COPD elsewhere in this project]

Adds to `universal.md`. The universal criteria still apply in full.

## CALL 911 IMMEDIATELY
- Lips or fingers turning blue or grey
- Too short of breath to finish a sentence
- Rescue inhaler does not help at all

## GO TO THE ER TODAY
- Coughing up more spit than usual, or it changed colour
- Needing the rescue inhaler far more than usual
- New chest tightness with more shortness of breath

## CALL YOUR DOCTOR
- Cough that is slowly getting better
- Feeling more tired than usual after walking

## Reviewer notes

- Oxygen saturation thresholds are deliberately NOT included. Most patients
  have no pulse oximeter at home, and a number the patient cannot measure is
  not an action they can take. **Reviewer: confirm, or supply a threshold and
  say what the patient should measure it with.**
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
