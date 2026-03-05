import google.genai as genai
import time
import logging
from config import GOOGLE_API_KEY, MODEL_NAME, DATA_PATH, FHIR_SPEC_PATH
from data_loader import load_mtsamples
from prompt_factory import build_fhir_r4_prompt
from fhir_utils import validate_fhir_bundle, run_custom_logical_validations

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_batch_experiment(n_notes=10):
    if not GOOGLE_API_KEY:
        logging.error("GOOGLE_API_KEY not found. Please set it in your .env file or environment variables.")
        return

    client = genai.Client(api_key=GOOGLE_API_KEY)
    df = load_mtsamples(DATA_PATH)
    sampled_notes = df.sample(n=n_notes)
    
    success_count = 0
    failed_cases = []
    start_time = time.time()

    logging.info(f"Starting batch validation for {n_notes} notes...")

    for index, row in sampled_notes.iterrows():
        note_text = row["transcription"]
        logging.info(f"Processing Note Index: {index}...")

        prompt = build_fhir_r4_prompt(note_text, FHIR_SPEC_PATH)
        
        try:
            response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
            raw_output = response.text
            
            validated_data = validate_fhir_bundle(raw_output)
            if validated_data:
                logical_errors = run_custom_logical_validations(validated_data)
                if not logical_errors:
                    logging.info(f"Index {index}: ✅ Passed!")
                    success_count += 1
                else:
                    failed_cases.append({"index": index, "error": "Logical", "msg": logical_errors})
            else:
                failed_cases.append({"index": index, "error": "Schema", "output": raw_output})
                
        except Exception as e:
            logging.error(f"Index {index}: ❌ API Error: {e}")
            failed_cases.append({"index": index, "error": "API", "msg": str(e)})

        time.sleep(2) # Rate limit protection

    total_time = time.time() - start_time
    print_results(n_notes, success_count, failed_cases, total_time)

def print_results(total, success, failed, duration):
    print("\n" + "="*30)
    print("📊 EXPERIMENT RESULTS")
    print("="*30)
    print(f"Total Processed: {total}")
    print(f"Success Rate: {(success/total)*100:.1f}%")
    print(f"Total Runtime: {duration:.2f}s")
    
    if failed:
        print("\n🚨 FAILURES:")
        for f in failed:
            print(f"- Index {f['index']}: {f['error']} Error")

if __name__ == "__main__":
    run_batch_experiment(5)