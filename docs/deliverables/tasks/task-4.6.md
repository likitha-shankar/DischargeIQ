# Task 4.6 - Integration Readiness and Vertex/BAA Runbook ✅

**Deliverable:** documentation mapping the standalone summer build to a
future EHR integration, plus the Vertex/BAA operating runbook.

**Artifact:** `docs/INTEGRATION_READINESS.md`

**Scope discipline:** no integration happens this summer and no dates are
committed. The document describes what would be involved, not what is
promised.

## The compliance-relevant part

Every agent runs on **Vertex AI under a GCP project with a BAA** - the
required path for real patient data. `LLM_PROVIDER=vertex` in production;
Anthropic is the FALLBACK provider only, used for one automatic cross-provider
retry when Vertex fails after its own retries.

**This is worth stating precisely because it was misstated at the 26 Aug
review**, where it was recorded as "Claude is the main model for extraction,
Gemini for the chatbot". That is not what ships, and if it reaches a written
record it misstates both the architecture and the BAA story.

No API key exists for the LLM path at all - authentication is ADC. The
`GOOGLE_API_KEY` that once existed was deleted 16 Aug 2026.

## FHIR, added 6 Sep 2026

`dischargeiq/utils/fhir_adapter.py` maps a FHIR R4 bundle straight to
`ExtractionOutput`, covering MedicationRequest, Condition, Encounter,
Appointment and Procedure. Liebovitz item 3.4.

**The finding is worth more than the adapter.** A bundle removes extraction
error for dose, date and provider entirely - it does not shrink, it
disappears. But no discrete FHIR resource carries red flags, activity limits
or dietary restrictions; those live in narrative discharge instructions. So
the safety-critical agent gains **nothing** from FHIR, and PDF has to remain
the fallback because healthcare still faxes.

The adapter reports what it cannot supply (`FhirCoverage.needs_narrative`)
rather than returning a confident empty list.
