#!/usr/bin/env python3
"""
Inspect Kaggle CSV structure: print column names and sample values for building column mapping.

Run from project root (or from /app in Docker):
  python scripts/inspect_kaggle_csv.py kaggle_data_engineer
  docker compose run --rm app python scripts/inspect_kaggle_csv.py kaggle_data_engineer

Requires KAGGLE_USERNAME and KAGGLE_API_TOKEN (or KAGGLE_KEY) if the dataset is not yet downloaded.
"""

import os
import sys
from pathlib import Path

# Allow running from project root or from /app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/inspect_kaggle_csv.py <source>")
        print("  source: kaggle_data_engineer | kaggle_linkedin | kaggle_linkedin_skills")
        sys.exit(1)
    source = sys.argv[1].strip().lower()

    import pandas as pd

    if source == "kaggle_data_engineer":
        from ingestion.sources.kaggle_data_engineer_2023 import (
            DATASET,
            KAGGLE_BASE,
            download_dataset,
            _find_best_csv,
        )
        dest = Path(KAGGLE_BASE) / "lukkardata-data-engineer-job-postings-2023"
    elif source == "kaggle_linkedin":
        from ingestion.sources.kaggle_linkedin_postings import (
            DATASET,
            KAGGLE_BASE,
            download_dataset,
        )
        dest = Path(KAGGLE_BASE) / "arshkon-linkedin-job-postings"
        def _find_best_csv(d):
            csvs = sorted(d.rglob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)
            return csvs[0] if csvs else None
    elif source == "kaggle_linkedin_skills":
        from ingestion.sources.kaggle_linkedin_jobs_skills_2024 import (
            DATASET,
            KAGGLE_BASE,
            download_dataset,
        )
        dest = Path(KAGGLE_BASE) / "asaniczka-1-3m-linkedin-jobs-and-skills-2024"
        def _find_best_csv(d):
            csvs = sorted(d.rglob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)
            return csvs[0] if csvs else None
    else:
        print(f"Unknown source: {source}")
        sys.exit(1)

    if not dest.exists():
        print(f"Downloading {DATASET} to {dest} ...")
        download_dataset(DATASET)
    csv_path = _find_best_csv(dest)
    if not csv_path:
        print(f"No CSV found under {dest}")
        sys.exit(1)

    print(f"CSV: {csv_path}")
    print(f"Size: {csv_path.stat().st_size / 1024:.1f} KB")
    df = pd.read_csv(csv_path, nrows=3, low_memory=False)
    print(f"Rows (sample): {len(df)}")
    print(f"Columns ({len(df.columns)}):")
    for i, c in enumerate(df.columns):
        sample = df[c].iloc[0] if len(df) > 0 else ""
        if pd.isna(sample):
            sample_str = "<null>"
        else:
            s = str(sample).strip()
            sample_str = (s[:60] + "…") if len(s) > 60 else s
        print(f"  {i+1:3}. {repr(c):50} -> {sample_str}")
    print("\nCopy the column names above to build the mapping (canonical: job_title, job_description, company_name, location, salary_info, posted_date, job_url, skills).")

if __name__ == "__main__":
    main()
