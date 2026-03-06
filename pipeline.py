import uuid
import logging
from google.genai import Client
from config import GOOGLE_API_KEY, MODEL_NAME
from prompt_factory import build_extraction_prompt
from models import ClinicalExtraction

# FHIR Resources
from fhir.resources.R4B.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.practitioner import Practitioner
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.medicationrequest import MedicationRequest
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.procedure import Procedure
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.reference import Reference

class FHIRPipeline:
    def __init__(self):
        self.client = Client(api_key=GOOGLE_API_KEY)
        self.model = MODEL_NAME

    def run_pipeline(self, text: str):
        logging.info("Starting Clinical Extraction Stage...")
        raw_extraction = self._extract_clinical_info(text)
        if not raw_extraction:
            return None
        
        logging.info("Starting FHIR Assembly Stage...")
        bundle = self._assemble_fhir_bundle(raw_extraction)
        return bundle

    def _extract_clinical_info(self, text: str) -> ClinicalExtraction:
        prompt = build_extraction_prompt(text)
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": ClinicalExtraction.model_json_schema()
                }
            )
            # Use model_validate_json for more robust parsing
            return ClinicalExtraction.model_validate_json(response.text)
        except Exception as e:
            logging.error(f"Extraction failed: {e}")
            return None

    def _assemble_fhir_bundle(self, extraction: ClinicalExtraction) -> Bundle:
        entries = []
        patient_uuid = f"urn:uuid:{uuid.uuid4()}"
        encounter_uuid = f"urn:uuid:{uuid.uuid4()}"
        
        # 1. Patient
        patient_res = Patient()
        patient_res.id = str(uuid.uuid4())
        if extraction.patient:
            if extraction.patient.name:
                patient_res.name = [{"text": extraction.patient.name}]
            if extraction.patient.gender:
                patient_res.gender = extraction.patient.gender
            if extraction.patient.birthDate:
                patient_res.birthDate = extraction.patient.birthDate
        
        entries.append(self._create_bundle_entry(patient_res, patient_uuid))

        # 2. Practitioner(s)
        practitioner_map = {} # name -> uuid
        for prac in extraction.practitioners:
            p_res = Practitioner()
            p_res.id = str(uuid.uuid4())
            p_res.name = [{"text": prac.name}]
            p_uuid = f"urn:uuid:{p_res.id}"
            practitioner_map[prac.name] = p_uuid
            entries.append(self._create_bundle_entry(p_res, p_uuid))

        # 3. Encounter
        encounter_res = Encounter(status="finished", class_fhir={"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": extraction.encounter_class})
        encounter_res.subject = Reference(reference=patient_uuid)
        entries.append(self._create_bundle_entry(encounter_res, encounter_uuid))

        # 4. Conditions
        for cond in extraction.conditions:
            c_res = Condition(
                clinicalStatus={"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": cond.status}]},
                subject=Reference(reference=patient_uuid),
                encounter=Reference(reference=encounter_uuid)
            )
            c_res.code = CodeableConcept(text=cond.description)
            if cond.code:
                c_res.code.coding = [Coding(system="http://snomed.info/sct", code=cond.code)]
            entries.append(self._create_bundle_entry(c_res))

        # 5. Medications
        for med in extraction.medication_requests:
            m_res = MedicationRequest(
                status=med.status, 
                intent="order",
                medicationCodeableConcept=CodeableConcept(text=med.name),
                subject=Reference(reference=patient_uuid),
                encounter=Reference(reference=encounter_uuid)
            )
            if med.dosage:
                m_res.dosageInstruction = [{"text": med.dosage}]
            entries.append(self._create_bundle_entry(m_res))

        # 6. Observations
        for obs in extraction.observations:
            o_res = Observation(
                status="final", 
                category=[{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
                subject=Reference(reference=patient_uuid),
                encounter=Reference(reference=encounter_uuid),
                code=CodeableConcept(text=obs.type)
            )
            if obs.code:
                o_res.code.coding = [Coding(system="http://loinc.org", code=obs.code)]
            
            # Handle numeric vs string values robustly
            val_raw = obs.value
            if isinstance(val_raw, (int, float)):
                o_res.valueQuantity = {"value": float(val_raw), "unit": obs.unit}
            elif isinstance(val_raw, str):
                # String cleaning for manual numeric checks
                val_clean = val_raw.replace('.','',1)
                if val_clean.isdigit() or (val_clean.startswith('-') and val_clean[1:].isdigit()):
                    o_res.valueQuantity = {"value": float(val_raw), "unit": obs.unit}
                else:
                    o_res.valueString = val_raw
            else:
                o_res.valueString = str(val_raw)
            
            entries.append(self._create_bundle_entry(o_res))

        # 7. Procedures
        for proc in extraction.procedures:
            p_res = Procedure(
                status=proc.status,
                subject=Reference(reference=patient_uuid),
                encounter=Reference(reference=encounter_uuid),
                code=CodeableConcept(text=proc.description)
            )
            if proc.date:
                # Basic ISO date check: YYYY-MM-DD
                if len(proc.date) == 10 and proc.date[4] == '-' and proc.date[7] == '-':
                    p_res.performedDateTime = proc.date
                else:
                    p_res.performedString = proc.date
            entries.append(self._create_bundle_entry(p_res))

        # Create Bundle
        bundle = Bundle(type="transaction", entry=entries)
        return bundle

    def _create_bundle_entry(self, resource, full_url=None):
        if not full_url:
            full_url = f"urn:uuid:{uuid.uuid4()}"
        return BundleEntry(
            fullUrl=full_url,
            resource=resource,
            request=BundleEntryRequest(method="POST", url=resource.get_resource_type())
        )

pipeline = FHIRPipeline()
