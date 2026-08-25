<!--
File: templates/escalation/_FORMAT.md
Owner: Likitha Shankar
Description: The format every escalation-tier template follows, and what a
  reviewer is being asked to sign. Files starting with "_" are documentation
  and are skipped by the loader.
Used by: dischargeiq/utils/escalation_templates.py (parser contract)
Critical rules: tier headers are fixed strings; a template is inert until the
  sign-off block names a real reviewer AND a real date.
-->

# Escalation template format

## What these files are for

Item 2.2 of the Dr. Liebovitz faculty review (22 Aug 2026):

> The three-tier escalation guide is the highest-risk output because it
> delivers triage advice to a patient with no clinician in the loop. Anchor
> each tier to symptom criteria drawn from the source document or from a
> clinician-authored template rather than generated text, and require
> physician sign-off on the template.

Before these files existed, the tier criteria lived inside
`dischargeiq/prompts/agent5_system_prompt.txt`. They were real criteria, but
they sat in a prompt: unsigned, editable by anyone, invisible to a clinician,
and with no record of who agreed to them. These files move the same criteria
somewhere a physician can read, correct and sign.

## The rule that makes this worth doing

**An unsigned template is inert.** `escalation_templates.py` treats a template
as authoritative only when its sign-off block names a real reviewer and a real
date. Until then Agent 5 behaves exactly as it did before.

This matters more than it might look. A template drafted in-repo and then used
as authoritative would be *worse* than generated text: identical clinical risk,
now wearing a "clinician-reviewed" label. Nothing about patient-facing output
changes on the day a template file is added. It changes on the day a physician
signs it.

## What a reviewer is being asked to do

For each tier, confirm that every criterion belongs in that tier for this
diagnosis, and add anything missing. The three tiers are:

- **CALL 911 IMMEDIATELY** - life-threatening, minutes matter
- **GO TO THE ER TODAY** - hours, not minutes, and not tomorrow
- **CALL YOUR DOCTOR** - office hours, and explicitly not an ER visit

Tier 1 is the one the system enforces. `verify_guide()` checks that no Tier 1
criterion was demoted or dropped from a generated guide, because that is the
failure with the worst consequence and the clearest definition. Tiers 2 and 3
are guidance to the agent, not enforced constraints.

## File format

```markdown
# <Diagnosis> - Escalation Tier Template

**Guideline reference:** <guideline, e.g. ACC/AHA 2022>

## CALL 911 IMMEDIATELY
- <criterion, plain language, one per line>

## GO TO THE ER TODAY
- <criterion>

## CALL YOUR DOCTOR
- <criterion>

## Reviewer notes
- <anything the reviewer should know, and anything changed after review>

## Clinical sign-off

**Reviewed by:** [Pending - Dr. Liebovitz / designated reviewer]
**Date:** [Pending]
**Status:** Awaiting faculty review
```

Rules the parser depends on:

- Tier headers are `## ` plus the exact fixed string. They are also parsed by
  `streamlit_app.py` and the Flutter results screen, so they never change.
- Criteria are `- ` bullets under a tier header.
- `**Reviewed by:**` and `**Date:**` must BOTH be filled for the template to
  become authoritative. A bracketed placeholder counts as empty, which is why
  `[Pending]` is the default rather than a blank line.

This mirrors the sign-off convention already used by the diagnosis explanation
templates one directory up.

## Provenance of the current drafts

Every criterion in the current drafts was taken from the tier lists already
present in `agent5_system_prompt.txt`, which is shipped and in use. They were
restructured, not authored: this is a reorganisation of existing system
behaviour into a reviewable artefact, so that a clinician is reviewing what the
system actually does today rather than a fresh proposal.

**No draft in this directory has been reviewed by a clinician.** That is the
entire remaining work of item 2.2, and it cannot be done inside the repository.
