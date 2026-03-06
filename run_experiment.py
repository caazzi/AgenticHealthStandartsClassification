import time
import logging
import json
import pandas as pd
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from config import GOOGLE_API_KEY, MODEL_NAME, DATA_PATH, AUDIT_LOG_PATH
from data_loader import load_mtsamples

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from pipeline import pipeline
from evaluator import evaluator

# Lock for thread-safe writing to CSV and shared lists
csv_lock = Lock()

def save_audit_log(note_text, bundle_json=None, eval_results=None, extraction_thoughts=None, status="SUCCESS", error_msg=None, duration_sec=None):
    """Appends a single experiment result (success or fail) to the persistent audit CSV."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Extract score and analysis if available
    judge_score = eval_results['scores']['overall'] if eval_results else None
    judge_analysis = json.dumps({
        "strengths": eval_results.get('strengths', []),
        "weaknesses": eval_results.get('weaknesses', []),
        "recommendation": eval_results.get('recommendation', "")
    }) if eval_results else None
    
    judge_thoughts = eval_results.get("judge_thoughts") if eval_results else None

    new_data = {
        "timestamp": [timestamp],
        "status": [status],
        "duration_sec": [f"{duration_sec:.2f}" if duration_sec is not None else None],
        "extraction_thoughts": [extraction_thoughts],
        "judge_thoughts": [judge_thoughts],
        "note_sample": [note_text],
        "fhir_bundle": [bundle_json],
        "judge_score": [judge_score],
        "judge_analysis": [judge_analysis],
        "error_msg": [error_msg]
    }
    
    df = pd.DataFrame(new_data)
    
    # Define canonical column order
    cols = ["timestamp", "status", "duration_sec", "extraction_thoughts", "judge_thoughts", "note_sample", "fhir_bundle", "judge_score", "judge_analysis", "error_msg"]
    df = df[cols]
    
    with csv_lock:
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
                    logging.warning(f"Audit log schema mismatch (v0.8 - added thoughts). Backed up old log to {bak_path.name}")
            except Exception:
                df.to_csv(AUDIT_LOG_PATH, mode='w', header=True, index=False)
        else:
            df.to_csv(AUDIT_LOG_PATH, mode='w', header=True, index=False)

def process_single_note(note_data):
    """Processes a single clinical note: Extraction -> Assembly -> Evaluation."""
    index, row = note_data
    note_text = row["transcription"]
    logging.info(f"Processing Note Index: {index}...")
    
    note_start = time.time()
    extraction_thoughts = None
    try:
        bundle, extraction_thoughts = pipeline.run_pipeline(note_text)
        
        if bundle:
            bundle_json = bundle.model_dump_json(exclude_none=True)
            translation_duration = time.time() - note_start
            
            # Unified Evaluation (Structural + LLM-as-a-Judge)
            logging.info(f"Index {index}: ⚖️ Starting Evaluation (Judge: {evaluator.model_id})...")
            eval_results = evaluator.evaluate(note_text, bundle_json)
            
            if eval_results:
                logical_errors = eval_results.get("structural_errors", [])
                if logical_errors:
                    logging.error(f"Index {index}: ❌ Structural Errors: {logical_errors}")
                    save_audit_log(note_text, bundle_json, eval_results, extraction_thoughts, status="FAIL", error_msg=f"Structural Errors: {logical_errors}", duration_sec=translation_duration)
                    return {"index": index, "status": "FAIL", "error": "Structural", "msg": logical_errors}
                else:
                    logging.info(f"Index {index}: ✅ Passed (Structural) | ⭐ Score: {eval_results['scores']['overall']}/10")
                    save_audit_log(note_text, bundle_json, eval_results, extraction_thoughts, status="SUCCESS", duration_sec=translation_duration)
                    return {"index": index, "status": "SUCCESS", "eval": eval_results, "duration": translation_duration}
            else:
                logging.error(f"Index {index}: ❌ Evaluation Failed (Judge error)")
                save_audit_log(note_text, bundle_json, status="FAIL", extraction_thoughts=extraction_thoughts, error_msg="Judge failed to respond", duration_sec=translation_duration)
                return {"index": index, "status": "FAIL", "error": "Judge", "msg": "Judge failed to respond"}
        else:
            logging.error(f"Index {index}: ❌ Pipeline Failure (Extraction/Assembly)")
            translation_duration = time.time() - note_start
            save_audit_log(note_text, status="FAIL", extraction_thoughts=extraction_thoughts, error_msg="Failed to generate valid bundle", duration_sec=translation_duration)
            return {"index": index, "status": "FAIL", "error": "Pipeline", "msg": "Failed to generate valid bundle"}
            
    except Exception as e:
        logging.error(f"Index {index}: ❌ Error: {e}")
        translation_duration = time.time() - note_start
        save_audit_log(note_text, status="FAIL", extraction_thoughts=extraction_thoughts, error_msg=str(e), duration_sec=translation_duration)
        return {"index": index, "status": "FAIL", "error": "Exception", "msg": str(e)}

def run_batch_experiment(n_notes=5, parallel=False):
    if not GOOGLE_API_KEY:
        logging.error("GOOGLE_API_KEY not found. Please set it in your .env file or environment variables.")
        return

    df = load_mtsamples(DATA_PATH)
    sampled_notes = df.sample(n=min(n_notes, len(df)))
    
    success_count = 0
    failed_cases = []
    results_data = []
    start_time = time.time()

    logging.info(f"Starting batch validation using MODULAR PIPELINE for {n_notes} notes (Parallel={parallel})...")

    note_list = list(sampled_notes.iterrows())
    
    if parallel and n_notes > 1:
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Note: evaluate() might have rate limits, but user requested 2 parallel threads.
            results = list(executor.map(process_single_note, note_list))
    else:
        results = [process_single_note(note) for note in note_list]

    for res in results:
        if res["status"] == "SUCCESS":
            success_count += 1
            results_data.append(res)
        else:
            failed_cases.append(res)

    total_time = time.time() - start_time
    # Filter for durations (only available on successes in this implementation's return dict)
    durations = [res["duration"] for res in results if res["status"] == "SUCCESS"]
    avg_latency = sum(durations) / len(durations) if durations else 0
    
    print_results(n_notes, success_count, failed_cases, total_time, avg_latency, results_data)
    
    # Cleanup resources to avoid shutdown warnings
    pipeline.close()
    evaluator.close()

def print_results(total, success, failed, script_duration, avg_latency, results_data):
    print("\n" + "="*30)
    print("📊 EXPERIMENT RESULTS")
    print("="*30)
    print(f"Total Processed: {total}")
    print(f"Success Rate: {(success/total)*100:.1f}%")
    print(f"Avg Note-to-FHIR Latency: {avg_latency:.2f}s")
    print(f"Total Script Runtime: {script_duration:.2f}s")
    
    if results_data:
        avg_score = sum(r['eval']['scores']['overall'] for r in results_data) / len(results_data)
        print(f"Average Judge Score: {avg_score:.2f}/10")
        
        print("\n📈 DETAILED SCORES (with Latency):")
        for r in results_data:
            scores = r['eval']['scores']
            print(f"- Index {r['index']}: {scores['overall']}/10 | Latency: {r['duration']:.2f}s (Recall: {scores['recall']}, Prec: {scores['precision']})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FHIR Pipeline Experiment")
    parser.add_argument("--n", type=int, default=5, help="Number of notes to process (default: 5)")
    parser.add_argument("--parallel", action="store_true", help="Run with 2 parallel threads")
    args = parser.parse_args()

    run_batch_experiment(n_notes=args.n, parallel=args.parallel)