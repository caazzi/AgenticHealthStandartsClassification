from pydantic import BaseModel, Field
from typing import List, Optional, Union

class PatientInfo(BaseModel):
    name: Optional[str] = Field(None, description="Full name of the patient")
    gender: Optional[str] = Field(None, description="Gender (male, female, other, unknown)")
    birthDate: Optional[str] = Field(None, description="Birth date in YYYY-MM-DD format")

class PractitionerInfo(BaseModel):
    name: Optional[str] = Field(None, description="Full name of the practitioner")
    role: Optional[str] = Field(None, description="Role of the practitioner (e.g., Surgeon, Physician)")

class ConditionInfo(BaseModel):
    description: str = Field(..., description="Description of the condition or diagnosis")
    code: Optional[str] = Field(None, description="SNOMED or other code if identified")
    status: str = Field("active", description="Clinical status of the condition")

class MedicationInfo(BaseModel):
    name: str = Field(..., description="Name of the medication")
    dosage: Optional[str] = Field(None, description="Dosage instructions")
    route: Optional[str] = Field(None, description="Route of administration (e.g., oral)")
    status: str = Field("active", description="Status of the medication request")

class ObservationInfo(BaseModel):
    type: str = Field(..., description="Type of observation (e.g., Heart Rate, BP)")
    value: Union[str, float] = Field(..., description="Measured value")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    code: Optional[str] = Field(None, description="LOINC or other code if identified")

class ProcedureInfo(BaseModel):
    description: str = Field(..., description="Description of the procedure performed")
    date: Optional[str] = Field(None, description="Date of the procedure")
    status: str = Field("completed", description="Status of the procedure")

class ClinicalExtraction(BaseModel):
    patient: Optional[PatientInfo] = None
    practitioners: List[PractitionerInfo] = []
    conditions: List[ConditionInfo] = []
    medication_requests: List[MedicationInfo] = []
    observations: List[ObservationInfo] = []
    procedures: List[ProcedureInfo] = []
    encounter_class: str = Field("AMB", description="Encounter class (e.g., AMB, IMP)")
