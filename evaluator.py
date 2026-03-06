import google.genai as genai
import json
import logging
import re
import base64
from pydantic import BaseModel, Field
from typing import List, Optional
from config import GOOGLE_API_KEY, JUDGE_MODEL_NAME

class JudgeScores(BaseModel):
    recall: int = Field(..., ge=0, le=10)
    precision: int = Field(..., ge=0, le=10)
    referential_integrity: int = Field(..., ge=0, le=10)
    clinical_correctness: int = Field(..., ge=0, le=10)
    overall: float = Field(..., ge=0, le=10)

class JudgeEvaluation(BaseModel):
    scores: JudgeScores
    strengths: List[str]
    weaknesses: List[str]
    hallucinations: List[str]
    missed_entities: List[str]
    recommendation: str
    structural_errors: List[str] = []

class FHIRJudge:
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = JUDGE_MODEL_NAME

    def _run_structural_validations(self, bundle_dict):
        """Performs referential integrity and UUID format checks."""
        errors = []
        entries = bundle_dict.get("entry", [])

        if not entries:
            return ["Logical Error: Bundle contains no entries."]

        uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
        defined_urls = set()
        
        for entry in entries:
            if "fullUrl" in entry:
                defined_urls.add(entry["fullUrl"])
                if entry["fullUrl"].startswith("urn:uuid:"):
                    uuid_str = entry["fullUrl"].replace("urn:uuid:", "")
                    if not uuid_pattern.match(uuid_str):
                        errors.append(f"Logical Error: Invalid UUID format -> {uuid_str}")

            if "resource" in entry and "id" in entry["resource"]:
                res_type = entry["resource"]["resourceType"]
                res_id = entry["resource"]["id"]
                defined_urls.add(f"{res_type}/{res_id}")
                defined_urls.add(f"urn:uuid:{res_id}")

        def find_all_references(obj):
            refs = []
            if isinstance(obj, dict):
                if "reference" in obj and isinstance(obj["reference"], str):
                    refs.append(obj["reference"])
                for v in obj.values():
                    refs.extend(find_all_references(v))
            elif isinstance(obj, list):
                for item in obj:
                    refs.extend(find_all_references(item))
            return refs

        all_references = find_all_references(entries)
        for ref in all_references:
            if ref.startswith("http"): continue
            if ref not in defined_urls:
                errors.append(f"Logical Error: Broken Link! Reference '{ref}' missing.")

        return errors

    def evaluate(self, transcription, fhir_bundle_json):
        # 1. Structural Validation
        bundle_dict = json.loads(fhir_bundle_json)
        structural_errors = self._run_structural_validations(bundle_dict)

        # 2. Qualitative LLM Evaluation
        prompt = f"""
        You are a Chief Medical Informatics Officer (CMIO) acting as a gold-standard judge for clinical data extraction.
        
        ### TASK
        Compare the provided RAW MEDICAL TRANSCRIPTION against the GENERATED FHIR R4 BUNDLE.
        Evaluate the extraction for clinical accuracy, completeness, and structural integrity.
        
        ### RAW MEDICAL TRANSCRIPTION
        {transcription}
        
        ### GENERATED FHIR R4 BUNDLE
        {fhir_bundle_json}
        
        ### EVALUATION CRITERIA
        1. **Recall**: Were all clinically significant entities (diagnoses, medications, procedures, vitals) extracted?
        2. **Precision**: Is everything in the FHIR bundle actually present in the text? (No hallucinations)
        3. **Referential Integrity**: Are Resources correctly linked (e.g., Observation.subject points to Patient)?
        4. **Clinical Correctness**: Are the assigned codes (ICD-10/SNOMED) and values logically sound based on the text?
        """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": JudgeEvaluation.model_json_schema()
                }
            )
            
            # Extract parts without triggering warnings
            result_json = None
            thoughts = None
            
            for part in response.candidates[0].content.parts:
                if part.text:
                    result_json = part.text
                
                # Check for various forms of thoughts
                part_thoughts = getattr(part, 'thought_signature', None)
                if part_thoughts:
                    thoughts = base64.b64encode(part_thoughts).decode('utf-8')
                
                direct_thought = getattr(part, 'thought', None)
                if direct_thought:
                    thoughts = direct_thought

            if not result_json:
                logging.error("No JSON text found in judge response")
                return None

            eval_obj = JudgeEvaluation.model_validate_json(result_json)
            
            # Merge results
            eval_dict = eval_obj.model_dump()
            eval_dict["structural_errors"] = structural_errors
            eval_dict["judge_thoughts"] = thoughts
            
            return eval_dict
        except Exception as e:
            logging.error(f"Judge Error: {e}")
            return None

    def close(self):
        """Clean up resources."""
        self.client = None
        logging.info("FHIRJudge resources cleaned up.")

# Singleton instance
evaluator = FHIRJudge()
