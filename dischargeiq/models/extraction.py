"""
File: dischargeiq/models/extraction.py
Owner: Likitha Shankar
Description: Pydantic v2 models for Agent 1 structured extraction — SourceSpan,
  Medication, FollowUpAppointment, and ExtractionOutput define the locked JSON contract
  passed to scoped downstream agents; optional provenance fields support UI citations.
Key functions/classes: SourceSpan, Medication, FollowUpAppointment, ExtractionOutput
Edge cases handled:
  - Lists default to [] and optional scalars to None to avoid fabricated values.
Dependencies: pydantic
Called by: dischargeiq.agents.extraction_agent, orchestrator, main, db.history, streamlit.
"""

from pydantic import BaseModel
from typing import Optional, List


class SourceSpan(BaseModel):
    """
    Points back to the exact passage in the PDF that supports an extracted value.

    Used by the UI to show provenance — which page and which sentence each
    field came from. Prevents hallucination trust issues by making every
    extracted value traceable to the source document.
    """

    page: int        # 1-indexed page number within the PDF
    text: str        # verbatim quote from the document (one sentence or bullet)


class Medication(BaseModel):
    """A single medication entry extracted from the discharge document."""

    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    status: Optional[str] = None  # new | changed | continued | discontinued
    source: Optional[SourceSpan] = None  # provenance: page + verbatim text


class FollowUpAppointment(BaseModel):
    """A single follow-up appointment extracted from the discharge document."""

    provider: Optional[str] = None
    specialty: Optional[str] = None
    date: Optional[str] = None
    reason: Optional[str] = None
    source: Optional[SourceSpan] = None  # provenance: page + verbatim text


class ExtractionOutput(BaseModel):
    """
    Complete structured extraction from a hospital discharge document.

    Agent 1 populates this model. Fields not found in the source document
    must be null (for Optional fields) or [] (for List fields).
    Agent 1 must NEVER fabricate or infer values.

    Source span fields (patient_name_source, discharge_date_source,
    discharge_condition_source, primary_diagnosis_source, and source on each
    Medication and FollowUpAppointment) are Optional and default to None for
    backward compatibility — existing tests and downstream agents are unaffected.
    """

    patient_name: Optional[str] = None
    patient_name_source: Optional[SourceSpan] = None          # provenance for patient_name
    discharge_date: Optional[str] = None
    discharge_date_source: Optional[SourceSpan] = None        # provenance for discharge_date
    primary_diagnosis: str
    primary_diagnosis_source: Optional[SourceSpan] = None
    secondary_diagnoses: List[str] = []
    procedures_performed: List[str] = []
    medications: List[Medication] = []
    follow_up_appointments: List[FollowUpAppointment] = []
    activity_restrictions: List[str] = []
    dietary_restrictions: List[str] = []
    red_flag_symptoms: List[str] = []
    discharge_condition: Optional[str] = None
    discharge_condition_source: Optional[SourceSpan] = None   # provenance for discharge_condition
    extraction_warnings: List[str] = []
