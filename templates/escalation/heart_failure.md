<!--
File: templates/escalation/heart_failure.md
Owner: Likitha Shankar
Description: Heart-failure-specific escalation criteria, layered on universal.md.
Used by: dischargeiq/utils/escalation_templates.py
Critical rules: UNSIGNED - inert until a physician signs the block at the end.
-->

# Heart Failure - Escalation Tier Template

**Guideline reference:** [Pending reviewer confirmation - ACC/AHA 2022 is the
guideline named for heart failure elsewhere in this project]

Adds to `universal.md`. The universal criteria still apply in full.

## CALL 911 IMMEDIATELY
- Cannot breathe lying flat, and it is getting worse
- Coughing up pink or foamy spit

## GO TO THE ER TODAY
- Weight gain of 2 pounds or more in one day
- Weight gain of 5 pounds or more in one week
- Swelling in both legs that is much worse than usual

## CALL YOUR DOCTOR
- Needing an extra pillow to sleep
- Shoes or rings feeling tighter than usual

## Reviewer notes

- The 2 lb in one day threshold comes from the tier list already in
  `agent5_system_prompt.txt`, and `templates/heart_failure.md` records it as a
  Class I recommendation per ACC/AHA 2022. **Reviewer: confirm the threshold
  and confirm Tier 2 is the right tier for it.** The existing diagnosis
  template tells the patient to "call your doctor right away" for the same
  finding, which reads as Tier 3, so the two artefacts currently disagree.
- The 5 lb in one week criterion and the orthopnoea items (lying flat, extra
  pillow) are NOT in the current prompt. They are proposed additions drawn
  from the same clinical pattern. **Reviewer: accept, reject, or correct.**
  Flagged explicitly because everything else in this directory is a
  restructuring of shipped behaviour and these three lines are not.
- Pink or foamy sputum is proposed as Tier 1. Reviewer to confirm.

## Clinical sign-off

**Reviewed by:** [Pending - Dr. Liebovitz / designated reviewer]
**Date:** [Pending]
**Status:** Awaiting faculty review
**Changes made based on review:** [To be completed after faculty feedback]
