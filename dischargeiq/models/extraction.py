"""
Pydantic models for Agent 1 (Extraction) output.

This is the LOCKED schema — the contract between Agent 1 and all downstream
agents (2-5). Do not change field names or types without full team sign-off.

Depends on: pydantic v2.
"""

from pydantic import BaseModel
from typing import Optional, List


class Medication(BaseModel):
    """A single medication entry extracted from the discharge document."""

    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    status: Optional[str] = None  # new | changed | continued | discontinued


class FollowUpAppointment(BaseModel):
    """A single follow-up appointment extracted from the discharge document."""

    provider: Optional[str] = None
    specialty: Optional[str] = None
    date: Optional[str] = None
    reason: Optional[str] = None


class ExtractionOutput(BaseModel):
    """
    Complete structured extraction from a hospital discharge document.

    Agent 1 populates this model. Fields not found in the source document
    must be null (for Optional fields) or [] (for List fields).
    Agent 1 must NEVER fabricate or infer values.
    """

    patient_name: Optional[str] = None
    discharge_date: Optional[str] = None
    primary_diagnosis: str
    secondary_diagnoses: List[str] = []
    procedures_performed: List[str] = []
    medications: List[Medication] = []
    follow_up_appointments: List[FollowUpAppointment] = []
    activity_restrictions: List[str] = []
    dietary_restrictions: List[str] = []
    red_flag_symptoms: List[str] = []
    discharge_condition: Optional[str] = None
    extraction_warnings: List[str] = []
