from datetime import datetime

def build_extraction_prompt(text: str) -> str:
    """Generates the prompt for structured clinical extraction into JSON."""
    return f"""
You are an expert Medical Coder and Clinical Analyst.
Extract all relevant clinical information from the medical note provided below.

### EXTRACTION GUIDELINES
1. PATIENT: Extract name, gender, and birthDate if mentioned.
2. PRACTITIONERS: Identify all healthcare providers, their names and roles.
3. CONDITIONS: Extract all diagnoses, chief complaints, and symptoms.
4. MEDICATIONS: Extract drug name, dosage, and route.
5. OBSERVATIONS: Extract vital signs (HR, BP, Temp, lab results) with units.
6. PROCEDURES: Extract all performed medical actions and their dates.
7. ENCOUNTER: Determine if the encounter class is AMB (Ambulatory) or IMP (Inpatient).

MEDICAL NOTE:
{text}
"""