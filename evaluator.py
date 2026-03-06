import google.genai as genai
import json
import logging
from pydantic import BaseModel, Field
from typing import List
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

class FHIRJudge:
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = JUDGE_MODEL_NAME

    def evaluate(self, transcription, fhir_bundle_json):
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
            # Use model_validate_json for robust parsing
            eval_obj = JudgeEvaluation.model_validate_json(response.text)
            return eval_obj.model_dump()
        except Exception as e:
            logging.error(f"Judge Error: {e}")
            return None

# Singleton instance
evaluator = FHIRJudge()
