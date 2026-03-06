import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = "gemini-flash-latest"
JUDGE_MODEL_NAME = "gemini-pro-latest"

# Path Configuration
PROJECT_ROOT = Path(__file__).resolve().parent
RAW_DATA_PATH = PROJECT_ROOT / 'experiments' / 'data' / 'raw' / 'mtsamples.csv'
COMPLEX_DATA_PATH = PROJECT_ROOT / 'experiments' / 'data' / 'samples' / 'complex_notes.csv'
DATA_PATH = COMPLEX_DATA_PATH  # Re-routing main experiment to complex set
SAMPLE_DATA_PATH = PROJECT_ROOT / 'experiments' / 'data' / 'samples' / 'sample_notes.csv'
AUDIT_LOG_PATH = PROJECT_ROOT / 'experiments' / 'results' / 'audit_log.csv'