# Extraction Schema Notes

This document explains each field in `extraction_schema.json` — what it means, where to find it in a typical hospital discharge document, and how Agent 1 should handle it.

---

## Field Definitions

**patient_name**
The patient's full name, usually found in the header or cover page of the discharge document.

**discharge_date**
The date the patient was discharged from the facility, returned as an ISO 8601 date string (e.g. `"2024-03-15"`); typically labeled "Discharge Date" near the top of the document.

**primary_diagnosis**
The main condition the patient was treated for, often labeled "Principal Diagnosis" or "Discharge Diagnosis" in the clinical summary section.

**secondary_diagnoses**
A list of additional diagnoses documented alongside the primary condition, sometimes labeled "Secondary Diagnoses" or "Comorbidities."

**procedures_performed**
A list of medical procedures or surgeries carried out during the hospital stay, typically found in a "Procedures" or "Operative Report" section.

**medications**
A list of medications at discharge, each with the following sub-fields:
- `name`: The medication name (brand or generic).
- `dose`: The prescribed dose (e.g. `"10mg"`).
- `frequency`: How often it is taken (e.g. `"twice daily"`).
- `duration`: How long it should be taken (e.g. `"7 days"`).
- `status`: One of `new`, `changed`, `continued`, or `discontinued` — reflecting whether this medication is new at discharge, modified, carried over from before admission, or stopped.

**follow_up_appointments**
A list of scheduled or recommended follow-up visits, each with:
- `provider`: The name of the doctor or clinic.
- `specialty`: The medical specialty (e.g. `"Cardiology"`).
- `date`: The appointment date, if specified.
- `reason`: The stated purpose of the visit.

**activity_restrictions**
A list of physical activity limitations given to the patient at discharge (e.g. `"No lifting over 10 lbs for 4 weeks"`).

**dietary_restrictions**
A list of dietary instructions given at discharge (e.g. `"Low sodium diet"`, `"No alcohol"`).

**red_flag_symptoms**
A list of warning symptoms the patient is told to watch for and act on (e.g. `"Return to ER if fever exceeds 101°F"`), often found in a "When to Seek Emergency Care" section.

**discharge_condition**
A description or rating of the patient's condition at the time of discharge (e.g. `"Stable"`, `"Good"`, `"Fair"`).

**extraction_warnings**
A list of any fields Agent 1 could not confidently extract. This gets passed downstream so other agents know what data may be missing or uncertain. If everything was extracted cleanly, this should be an empty list `[]`.

---

## Null Rule (Required Reading)

Agent 1 must follow this rule strictly for every field:

- If a field **exists in the document but cannot be read clearly**, return `null`.
- If a field **does not appear in the document at all**, return `null`.
- **Agent 1 must never fabricate or guess a value.** A `null` is always safer than a wrong answer.
- For **list fields** (e.g. `medications`, `red_flag_symptoms`, `secondary_diagnoses`), return an empty list `[]` if nothing was found — not `null`.

Any field that could not be extracted with confidence should also be recorded in `extraction_warnings` with a brief note explaining what was missing or ambiguous.

---

## Sign-Off

Before Agent 1 development begins, both of the following must confirm they have read and agree to this schema:

- [ ] Backend Owner
- [ ] LLM Engineer