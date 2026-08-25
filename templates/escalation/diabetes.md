<!--
File: templates/escalation/diabetes.md
Owner: Likitha Shankar
Description: Diabetes-specific escalation criteria, layered on universal.md.
Used by: dischargeiq/utils/escalation_templates.py
Critical rules: UNSIGNED - inert until a physician signs the block at the end.
-->

# Diabetes - Escalation Tier Template

**Guideline reference:** [Pending reviewer confirmation - ADA 2024 is the guideline named for diabetes elsewhere in this project]

Adds to `universal.md`. The universal criteria still apply in full.

## CALL 911 IMMEDIATELY
- Cannot be woken up, or is confused and sweating
- Having a seizure
- Breathing fast and deep with fruity smelling breath

## GO TO THE ER TODAY
- Blood sugar stays very high and you are throwing up
- Blood sugar stays very low after eating sugar twice
- A foot sore that is red, warm, or draining

## CALL YOUR DOCTOR
- Blood sugar readings higher than usual for a few days
- Questions about when to take your diabetes medicine

## Reviewer notes

- Specific glucose numbers are deliberately NOT included. Target ranges differ
  per patient, and the 25 Aug corpus run showed the system inventing numeric
  thresholds absent from the source document. **Reviewer: supply the numbers
  if patient-specific targets can be safely generalised, or confirm that
  keeping this qualitative is correct.**
- The prompt already forbids the words hypoglycemia and hyperglycemia, so
  these criteria use plain descriptions instead.
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
