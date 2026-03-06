import pandas as pd
import os
import re

def curate():
    raw_path = "experiments/data/raw/mtsamples.csv"
    output_dir = "experiments/data/samples"
    output_path = os.path.join(output_dir, "complex_notes.csv")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"Reading {raw_path}...")
    df = pd.read_all_csv(raw_path) if hasattr(pd, 'read_all_csv') else pd.read_csv(raw_path)
    
    # Drop rows with empty transcriptions
    df = df.dropna(subset=['transcription'])
    
    # Logic for complexity:
    # 1. Length of transcription
    df['length'] = df['transcription'].apply(len)
    
    # 2. Section density (Count uppercase headers followed by colon)
    def count_sections(text):
        sections = re.findall(r'\b[A-Z\s]{4,}:', text)
        return len(set(sections))
    
    df['section_count'] = df['transcription'].apply(count_sections)
    
    # Normalize and score
    df['score'] = (df['length'] / df['length'].max()) + (df['section_count'] / df['section_count'].max())
    
    # Take top 1% (approx 50 samples out of ~5000)
    top_1_percent = int(len(df) * 0.01)
    complex_df = df.sort_values(by='score', ascending=False).head(top_1_percent)
    
    # Cleanup extra columns for output
    final_df = complex_df.drop(columns=['length', 'section_count', 'score'])
    
    print(f"Saving {len(final_df)} complex samples to {output_path}...")
    final_df.to_csv(output_path, index=False)
    print("Curation complete!")

if __name__ == "__main__":
    curate()
