from pydantic import BaseModel
from typing import Optional, List

class Medication(BaseModel):
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    status: Optional[str] = None

class FollowUpAppointment(BaseModel):
    provider: Optional[str] = None
    specialty: Optional[str] = None
    date: Optional[str] = None
    reason: Optional[str] = None

class ExtractionOutput(BaseModel):
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