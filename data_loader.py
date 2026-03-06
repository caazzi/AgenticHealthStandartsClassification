import pandas as pd
import os

def load_mtsamples(file_path: str) -> pd.DataFrame:
    """Loads the medical transcription dataset and preprocesses keywords."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dataset not found at: {file_path}")
    
    df = pd.read_csv(file_path, index_col=0)
    df['keywords'] = df['keywords'].fillna('').astype(str).str.split(',')
    return df