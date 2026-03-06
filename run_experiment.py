import time
import logging
import json
import pandas as pd
from datetime import datetime
from config import GOOGLE_API_KEY, MODEL_NAME, DATA_PATH, AUDIT_LOG_PATH
from data_loader import load_mtsamples
from fhir_utils import run_custom_logical_validations

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from pipeline import pipeline
from evaluator import evaluator

def save_audit_log(note_text, bundle_json=None, eval_results=None, status="SUCCESS", error_msg=None, duration_sec=None):
    """Appends a single experiment result (success or fail) to the persistent audit CSV."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Extract score and analysis if available
    judge_score = eval_results['scores']['overall'] if eval_results else None
    judge_analysis = json.dumps({
        "strengths": eval_results.get('strengths', []),
        "weaknesses": eval_results.get('weaknesses', []),
        "recommendation": eval_results.get('recommendation', "")
    }) if eval_results else None

    new_data = {
        "timestamp": [timestamp],
        "status": [status],
        "duration_sec": [f"{duration_sec:.2f}" if duration_sec is not None else None],
        "note_sample": [note_text],
        "fhir_bundle": [bundle_json],
        "judge_score": [judge_score],
        "judge_analysis": [judge_analysis],
        "error_msg": [error_msg]
    }
    
    df = pd.DataFrame(new_data)
    
    # Define canonical column order
    cols = ["timestamp", "status", "duration_sec", "note_sample", "fhir_bundle", "judge_score", "judge_analysis", "error_msg"]
    df = df[cols]
    
    # Append to CSV (check for header mismatch)
    if AUDIT_LOG_PATH.exists():
        try:
            existing_df = pd.read_csv(AUDIT_LOG_PATH, nrows=0)
            if list(existing_df.columns) == cols:
                df.to_csv(AUDIT_LOG_PATH, mode='a', header=False, index=False)
            else:
                # Schema mismatch: rename old file and start fresh
                bak_path = AUDIT_LOG_PATH.with_suffix(f'.csv.{int(time.time())}.bak')
                AUDIT_LOG_PATH.rename(bak_path)
                df.to_csv(AUDIT_LOG_PATH, mode='w', header=True, index=False)
                logging.warning(f"Audit log schema mismatch (v0.7). Backed up old log to {bak_path.name}")
        except Exception:
            df.to_csv(AUDIT_LOG_PATH, mode='w', header=True, index=False)
    else:
        df.to_csv(AUDIT_LOG_PATH, mode='w', header=True, index=False)

def run_batch_experiment(n_notes=5):
    if not GOOGLE_API_KEY:
        logging.error("GOOGLE_API_KEY not found. Please set it in your .env file or environment variables.")
        return

    df = load_mtsamples(DATA_PATH)
    sampled_notes = df.sample(n=n_notes)
    
    success_count = 0
    failed_cases = []
    results_data = []
    start_time = time.time()

    logging.info(f"Starting batch validation using MODULAR PIPELINE for {n_notes} notes...")

    for index, row in sampled_notes.iterrows():
        note_text = row["transcription"]
        logging.info(f"Processing Note Index: {index}...")
        
        note_start = time.time()  # Start timer for this note

        try:
            bundle = pipeline.run_pipeline(note_text)
            
            if bundle:
                validated_data = bundle.model_dump(exclude_none=True)
                logical_errors = run_custom_logical_validations(validated_data)
                
                if not logical_errors:
                    logging.info(f"Index {index}: ✅ Passed (Structural)")
                    
                    # LLM-as-a-Judge Evaluation
                    logging.info(f"Index {index}: ⚖️ Starting LLM Evaluation (Judge: {evaluator.model_id})...")
                    bundle_json = bundle.model_dump_json(exclude_none=True)
                    
                    # Capture translation latency before judge evaluation
                    translation_duration = time.time() - note_start
                    
                    eval_results = evaluator.evaluate(note_text, bundle_json)
                    
                    if eval_results:
                        logging.info(f"Index {index}: ⭐ Score: {eval_results['scores']['overall']}/10")
                        
                        # Save to Audit Log
                        save_audit_log(note_text, bundle_json, eval_results, status="SUCCESS", duration_sec=translation_duration)
                        
                        success_count += 1
                        results_data.append({
                            "index": index,
                            "eval": eval_results
                        })
                    else:
                        logging.error(f"Index {index}: ❌ Judge Failed")
                        save_audit_log(note_text, bundle_json, status="FAIL", error_msg="Judge failed to respond", duration_sec=translation_duration)
                        failed_cases.append({"index": index, "error": "Judge", "msg": "Judge failed to respond"})
                else:
                    logging.error(f"Index {index}: ❌ Logical Errors: {logical_errors}")
                    translation_duration = time.time() - note_start
                    save_audit_log(note_text, bundle_json, status="FAIL", error_msg=f"Logical Errors: {logical_errors}", duration_sec=translation_duration)
                    failed_cases.append({"index": index, "error": "Logical", "msg": logical_errors})
            else:
                logging.error(f"Index {index}: ❌ Pipeline Failure (Extraction/Assembly)")
                translation_duration = time.time() - note_start
                save_audit_log(note_text, status="FAIL", error_msg="Failed to generate valid bundle", duration_sec=translation_duration)
                failed_cases.append({"index": index, "error": "Pipeline", "msg": "Failed to generate valid bundle"})
                
        except Exception as e:
            logging.error(f"Index {index}: ❌ Error: {e}")
            translation_duration = time.time() - note_start
            save_audit_log(note_text, status="FAIL", error_msg=str(e), duration_sec=translation_duration)
            failed_cases.append({"index": index, "error": "Exception", "msg": str(e)})

        time.sleep(2) # Increased sleep for judge safety

    total_time = time.time() - start_time
    print_results(n_notes, success_count, failed_cases, total_time, results_data)

def print_results(total, success, failed, duration, results_data):
    print("\n" + "="*30)
    print("📊 EXPERIMENT RESULTS (COMPLEX SET)")
    print("="*30)
    print(f"Total Processed: {total}")
    print(f"Success Rate: {(success/total)*100:.1f}%")
    print(f"Total Runtime: {duration:.2f}s")
    
    if results_data:
        avg_score = sum(r['eval']['scores']['overall'] for r in results_data) / len(results_data)
        print(f"Average Judge Score: {avg_score:.2f}/10")
        
        print("\n📈 DETAILED SCORES:")
        for r in results_data:
            scores = r['eval']['scores']
            print(f"- Index {r['index']}: {scores['overall']}/10 (Recall: {scores['recall']}, Prec: {scores['precision']})")

if __name__ == "__main__":
    run_batch_experiment(5)