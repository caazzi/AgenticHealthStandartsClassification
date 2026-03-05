import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = "gemini-3-flash-preview"

# Path Configuration
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / 'experiments' / 'data' / 'raw' / 'mtsamples.csv'
SAMPLE_DATA_PATH = PROJECT_ROOT / 'experiments' / 'data' / 'samples' / 'sample_notes.csv'
FHIR_SPEC_PATH = PROJECT_ROOT / 'experiments' / 'data' / 'specs' / 'full_txt'