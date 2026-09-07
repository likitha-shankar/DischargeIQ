"""
File: dischargeiq/utils/fhir_adapter.py
Owner: Likitha Shankar
Description: Maps a FHIR R4 Bundle to ExtractionOutput, so a structured source
  can bypass Agent 1 entirely instead of being flattened to text and re-read by
  an LLM. Answers item 3.4 of the Dr. Liebovitz faculty review.
Key functions/classes: extraction_from_bundle, FhirCoverage
Edge cases handled:
  - Missing or unrecognisable resources yield null/[] rather than guesses.
  - Fields FHIR does not carry are reported as gaps, never fabricated.
Dependencies: dischargeiq.models.extraction. No network, no FHIR client.
Called by: not yet wired into the pipeline - see the note below.

WHY THIS EXISTS
---------------
Liebovitz, item 3.4: "Prefer structured source where it exists. Where a FHIR
endpoint is available, MedicationRequest, Encounter, Condition and Appointment
supply the same fields without OCR risk. Treat PDF as the fallback path rather
than the design centre."

He is right about the fields he named, and the win is larger than avoiding OCR.
A FHIR bundle needs NO extraction agent at all: dose, date and provider arrive
as typed values, so the entire class of extraction error disappears rather than
being reduced. Agents 2 to 5 consume ExtractionOutput and neither know nor care
where it came from.

WHAT FHIR DOES NOT SOLVE, which is the part worth knowing before betting on it
-----------------------------------------------------------------------------
Discrete FHIR resources carry medications, diagnoses, procedures and
appointments. They do NOT carry:

  - red_flag_symptoms    - what to watch for and when to call 911
  - activity_restrictions
  - dietary_restrictions

Those live in free-text discharge instructions, and in practice arrive as a
narrative blob (DocumentReference or Encounter text) that still needs reading.
So FHIR removes extraction risk from the medication tab and removes NOTHING
from the escalation guide, which is the highest-risk output in the product.

That is a genuine finding rather than a caveat: "prefer FHIR" makes the safe
parts safer and leaves the dangerous part exactly where it was.

NOT WIRED IN. This maps and reports coverage; nothing calls it from the
pipeline yet. Shipping a second ingestion path needs an endpoint, auth, and a
decision about what happens when a bundle is partial - none of which should be
invented here.
"""

from dataclasses import dataclass, field
from typing import Any

from dischargeiq.models.extraction import (
    ExtractionOutput,
    FollowUpAppointment,
    Medication,
    SourceSpan,
)

#: FHIR MedicationRequest.status values that mean the patient is to take it.
#: "stopped" and "cancelled" are deliberately excluded - a discontinued drug on
#: a discharge list is how a patient keeps taking something they should not.
_ACTIVE_MED_STATUSES = {"active", "completed", "on-hold", "draft", "unknown"}


@dataclass
class FhirCoverage:
    """
    What a bundle supplied and what it could not.

    Reported alongside the extraction so a caller can see that a "successful"
    FHIR ingest still leaves the escalation guide without input.
    """

    resources_seen: dict[str, int] = field(default_factory=dict)
    fields_populated: list[str] = field(default_factory=list)
    fields_unavailable: list[str] = field(default_factory=list)

    @property
    def needs_narrative(self) -> bool:
        """True when fields only free text can supply are missing."""
        return bool(self.fields_unavailable)


def _entries(bundle: dict, resource_type: str) -> list[dict]:
    """
    All resources of one type from a Bundle.

    Args:
        bundle: A FHIR Bundle as a dict.
        resource_type: e.g. "MedicationRequest".

    Returns:
        The matching resources, or [] when the bundle is malformed. A bad
        bundle yields nothing rather than raising - the caller has a PDF path
        to fall back to.
    """
    if not isinstance(bundle, dict):
        return []
    out = []
    for entry in bundle.get("entry") or []:
        resource = (entry or {}).get("resource") or {}
        if resource.get("resourceType") == resource_type:
            out.append(resource)
    return out


def _concept_text(concept: Any) -> str | None:
    """
    Human-readable text from a CodeableConcept.

    Prefers .text, then the first coding's .display. Falls back to a raw code
    only as a last resort, because a patient reading "I50.9" is not served.

    Args:
        concept: A CodeableConcept dict, or anything else.

    Returns:
        Display text, or None.
    """
    if not isinstance(concept, dict):
        return None
    if isinstance(concept.get("text"), str) and concept["text"].strip():
        return concept["text"].strip()
    for coding in concept.get("coding") or []:
        display = (coding or {}).get("display")
        if isinstance(display, str) and display.strip():
            return display.strip()
    for coding in concept.get("coding") or []:
        code = (coding or {}).get("code")
        if isinstance(code, str) and code.strip():
            return code.strip()
    return None


def _provenance(resource: dict) -> SourceSpan:
    """
    Provenance for a value that came from a FHIR resource, not a page.

    SourceSpan was built for PDFs and carries a page number. A FHIR value has
    no page, so page 0 marks "not from a document" and the text names the
    resource that supplied it. Inventing a page number would make the citation
    chips lie about where a fact came from, and those chips are the product's
    trust mechanism.

    Args:
        resource: The FHIR resource a value was read from.

    Returns:
        A SourceSpan pointing at the resource.
    """
    rtype = resource.get("resourceType", "Resource")
    rid = resource.get("id", "unknown")
    return SourceSpan(page=0, text=f"FHIR {rtype}/{rid}")


def _dose(dosage: dict) -> str | None:
    """Dose as "40 mg" from doseAndRate.doseQuantity, or None."""
    for entry in dosage.get("doseAndRate") or []:
        quantity = (entry or {}).get("doseQuantity") or {}
        value, unit = quantity.get("value"), quantity.get("unit")
        if value is not None:
            # Render 40.0 as "40": a patient should not read a float.
            number = int(value) if float(value).is_integer() else value
            return f"{number} {unit}".strip() if unit else str(number)
    return None


def _frequency(dosage: dict) -> str | None:
    """
    Frequency, preferring the human sentence the source already wrote.

    dosageInstruction.text is what a clinician typed and is more useful to a
    patient than a reconstruction from timing.repeat. The structured form is
    used only when no text exists.
    """
    text = dosage.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    repeat = (dosage.get("timing") or {}).get("repeat") or {}
    frequency, period, unit = (
        repeat.get("frequency"), repeat.get("period"), repeat.get("periodUnit"),
    )
    if frequency and period and unit:
        units = {"d": "day", "h": "hour", "wk": "week", "mo": "month"}
        noun = units.get(unit, unit)
        times = "once" if frequency == 1 else f"{frequency} times"
        every = f"every {period} {noun}" if period != 1 else f"a {noun}"
        return f"{times} {every}"
    return None


def _medications(bundle: dict) -> list[Medication]:
    """MedicationRequest resources the patient is meant to take."""
    meds = []
    for request in _entries(bundle, "MedicationRequest"):
        status = (request.get("status") or "unknown").lower()
        if status not in _ACTIVE_MED_STATUSES:
            # Skipped on purpose. A stopped drug appearing on a discharge list
            # is how a patient keeps taking something they were told to stop.
            continue
        name = _concept_text(request.get("medicationCodeableConcept"))
        if not name:
            # medicationReference points at a separate Medication resource we
            # may not have been given. Recording the drug without a name would
            # be worse than recording nothing.
            continue
        dosage = (request.get("dosageInstruction") or [{}])[0] or {}
        meds.append(Medication(
            name=name,
            dose=_dose(dosage),
            frequency=_frequency(dosage),
            duration=None,
            status="continued" if status == "active" else None,
            source=_provenance(request),
        ))
    return meds


def _appointments(bundle: dict) -> list[FollowUpAppointment]:
    """Appointment resources as follow-up visits."""
    appointments = []
    for appt in _entries(bundle, "Appointment"):
        provider = None
        for participant in appt.get("participant") or []:
            actor = (participant or {}).get("actor") or {}
            display = actor.get("display")
            if isinstance(display, str) and display.strip():
                provider = display.strip()
                break
        service = None
        for concept in appt.get("serviceType") or []:
            service = _concept_text(concept)
            if service:
                break
        reason = appt.get("description")
        if not reason:
            for concept in appt.get("reasonCode") or []:
                reason = _concept_text(concept)
                if reason:
                    break
        start = appt.get("start")
        appointments.append(FollowUpAppointment(
            provider=provider,
            specialty=service,
            # Date only. A discharge summary says "2026-09-15", not an instant,
            # and the appointment card renders a day.
            date=start.split("T")[0] if isinstance(start, str) else None,
            reason=reason,
            source=_provenance(appt),
        ))
    return appointments


def _diagnoses(bundle: dict) -> tuple[str | None, list[str], dict | None]:
    """
    Primary and secondary diagnoses.

    Encounter.diagnosis[].rank decides the primary when present, because that
    is where the discharging clinician recorded it. Without a rank there is no
    reliable way to know, so the first Condition is used and the caller is told
    the choice was arbitrary rather than being given false confidence.

    Returns:
        (primary, secondaries, the resource the primary came from).
    """
    conditions = _entries(bundle, "Condition")
    if not conditions:
        return None, [], None

    by_ref = {f"Condition/{c.get('id')}": c for c in conditions if c.get("id")}
    ranked: list[tuple[int, dict]] = []
    for encounter in _entries(bundle, "Encounter"):
        for diagnosis in encounter.get("diagnosis") or []:
            ref = ((diagnosis or {}).get("condition") or {}).get("reference")
            rank = (diagnosis or {}).get("rank")
            if ref in by_ref and isinstance(rank, int):
                ranked.append((rank, by_ref[ref]))

    if ranked:
        ranked.sort(key=lambda pair: pair[0])
        primary_resource = ranked[0][1]
    else:
        primary_resource = conditions[0]

    primary = _concept_text(primary_resource.get("code"))
    secondaries = []
    for condition in conditions:
        if condition is primary_resource:
            continue
        text = _concept_text(condition.get("code"))
        if text and text != primary:
            secondaries.append(text)
    return primary, secondaries, primary_resource


def extraction_from_bundle(bundle: dict) -> tuple[ExtractionOutput, FhirCoverage]:
    """
    Build an ExtractionOutput from a FHIR R4 Bundle, with a coverage report.

    Args:
        bundle: A FHIR Bundle as a dict.

    Returns:
        (extraction, coverage). The extraction is shaped exactly as Agent 1's
        output, so agents 2-5 need no changes. The coverage says which fields
        the bundle could not supply.

    Raises:
        ValueError: If no Condition yields a primary diagnosis. Every
            downstream agent requires one, and a bundle without it is not a
            discharge summary - failing here is clearer than emitting a record
            that quietly explains nothing.
    """
    primary, secondaries, primary_resource = _diagnoses(bundle)
    if not primary:
        raise ValueError(
            "FHIR bundle has no Condition with a usable code; a primary "
            "diagnosis is required by every downstream agent."
        )

    medications = _medications(bundle)
    appointments = _appointments(bundle)
    procedures = [
        text for text in (
            _concept_text(p.get("code")) for p in _entries(bundle, "Procedure")
        ) if text
    ]

    patient_name = None
    patients = _entries(bundle, "Patient")
    if patients:
        names = patients[0].get("name") or []
        if names:
            name = names[0] or {}
            if isinstance(name.get("text"), str):
                patient_name = name["text"]
            else:
                given = " ".join(name.get("given") or [])
                patient_name = f"{given} {name.get('family', '')}".strip() or None

    discharge_date = None
    discharge_condition = None
    encounters = _entries(bundle, "Encounter")
    if encounters:
        encounter = encounters[0]
        end = (encounter.get("period") or {}).get("end")
        if isinstance(end, str):
            discharge_date = end.split("T")[0]
        hospitalization = encounter.get("hospitalization") or {}
        discharge_condition = _concept_text(
            hospitalization.get("dischargeDisposition")
        )

    counts: dict[str, int] = {}
    for entry in (bundle.get("entry") or []):
        rtype = ((entry or {}).get("resource") or {}).get("resourceType")
        if rtype:
            counts[rtype] = counts.get(rtype, 0) + 1

    populated = [name for name, value in (
        ("primary_diagnosis", primary),
        ("secondary_diagnoses", secondaries),
        ("medications", medications),
        ("follow_up_appointments", appointments),
        ("procedures_performed", procedures),
        ("patient_name", patient_name),
        ("discharge_date", discharge_date),
        ("discharge_condition", discharge_condition),
    ) if value]

    # The fields no discrete FHIR resource carries. Always reported, never
    # guessed. These are exactly Agent 5's inputs, which is why "prefer FHIR"
    # does not make the escalation guide safer.
    unavailable = ["red_flag_symptoms", "activity_restrictions",
                   "dietary_restrictions"]

    warnings = [
        "Source: FHIR bundle, not a document. Fields are typed values, so no "
        "extraction error is possible for them.",
        "FHIR carries no warning signs, activity restrictions or dietary "
        "restrictions. Those need the narrative discharge instructions, and "
        "the escalation guide has no input without them.",
    ]
    if not ranked_primary_was_explicit(bundle):
        warnings.append(
            "No Encounter.diagnosis rank was present, so the primary diagnosis "
            "is the first Condition in the bundle and may not be the one the "
            "discharging clinician considered principal."
        )

    extraction = ExtractionOutput(
        patient_name=patient_name,
        discharge_date=discharge_date,
        primary_diagnosis=primary,
        primary_diagnosis_source=_provenance(primary_resource) if primary_resource else None,
        secondary_diagnoses=secondaries,
        procedures_performed=procedures,
        medications=medications,
        follow_up_appointments=appointments,
        activity_restrictions=[],
        dietary_restrictions=[],
        red_flag_symptoms=[],
        discharge_condition=discharge_condition,
        extraction_warnings=warnings,
    )
    coverage = FhirCoverage(
        resources_seen=counts,
        fields_populated=populated,
        fields_unavailable=unavailable,
    )
    return extraction, coverage


def ranked_primary_was_explicit(bundle: dict) -> bool:
    """
    Whether the bundle actually said which diagnosis is primary.

    Args:
        bundle: A FHIR Bundle.

    Returns:
        True when an Encounter.diagnosis carries a rank. Callers use this to
        decide whether the primary diagnosis is authoritative or a guess.
    """
    for encounter in _entries(bundle, "Encounter"):
        for diagnosis in encounter.get("diagnosis") or []:
            if isinstance((diagnosis or {}).get("rank"), int):
                return True
    return False
