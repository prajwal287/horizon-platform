#!/usr/bin/env python3
"""
Compare taxonomy vs LLM skills extraction on Kaggle Data Engineer 2023 sample.

Reads Kaggle DE data from CSV (downloads if needed), runs both extractors on a sample,
writes a comparison CSV with row_id, job_title, description_snippet, skills_taxonomy,
skills_llm, and jaccard_similarity. Optional: --from-bigquery to read from raw_kaggle_data_engineer_2023.

Usage:
  python scripts/compare_skills_extraction.py [--sample 300] [--output comparison_skills.csv]
  python scripts/compare_skills_extraction.py --from-bigquery --sample 200

Requires GOOGLE_API_KEY or GEMINI_API_KEY for LLM extraction. For CSV, KAGGLE_USERNAME and KAGGLE_API_TOKEN.
"""

import argparse
import csv
import logging
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _jaccard(a: list[str], b: list[str]) -> float:
    """Jaccard similarity between two skill lists (set intersection / set union)."""
    sa = set(s.strip().lower() for s in a if s and s.strip())
    sb = set(s.strip().lower() for s in b if s and s.strip())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _load_sample_from_csv(sample_size: int) -> list[tuple[int, Optional[str], Optional[str]]]:
    """Load sample (row_id, title, description) from Kaggle DE CSV.
    Uses existing data/kaggle/... if present (no Kaggle auth). Only imports Kaggle API when download is needed.
    """
    import pandas as pd

    kaggle_base = os.environ.get("KAGGLE_DATA_PATH", os.path.join(os.getcwd(), "data", "kaggle"))
    dest = Path(kaggle_base) / "lukkardata-data-engineer-job-postings-2023"
    csv_path = None
    if dest.exists():
        csvs = sorted(dest.rglob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)
        csv_path = csvs[0] if csvs else None

    if not csv_path:
        logger.info("Dataset not found locally. Downloading via Kaggle API (requires kaggle.json or KAGGLE_USERNAME + KAGGLE_KEY) ...")
        from ingestion.sources.kaggle_data_engineer_2023 import (
            DATASET,
            KAGGLE_BASE,
            _find_best_csv,
            _norm_col,
            _normalize_columns,
        )
        from ingestion.sources.kaggle_download import download_dataset

        download_dataset(DATASET)
        csv_path = _find_best_csv(dest)
        if not csv_path:
            raise FileNotFoundError(f"No CSV under {dest}")
        col_map = _normalize_columns(pd.read_csv(csv_path, nrows=1, low_memory=False))
    else:
        col_map = None

    df = pd.read_csv(csv_path, nrows=sample_size * 3, low_memory=False)
    if col_map is None:
        title_col = "Job_details" if "Job_details" in df.columns else df.columns[0]
        description_col = "Job_details.1" if "Job_details.1" in df.columns else (df.columns[1] if len(df.columns) > 1 else None)
    else:
        title_col = None
        description_col = None
        for c, canon in col_map.items():
            if canon == "job_title":
                title_col = c
            elif canon == "job_description":
                description_col = c
        if not title_col:
            title_col = "Job_details" if "Job_details" in df.columns else df.columns[0]
        if not description_col:
            description_col = "Job_details.1" if "Job_details.1" in df.columns else None

    rows: list[tuple[int, Optional[str], Optional[str]]] = []
    for idx, row in df.iterrows():
        if len(rows) >= sample_size:
            break
        title = row.get(title_col) if title_col else None
        desc = row.get(description_col) if description_col else None
        if pd.isna(title) and pd.isna(desc):
            continue
        title_s = str(title).strip() if not pd.isna(title) else None
        desc_s = str(desc).strip() if not pd.isna(desc) and str(desc).strip() else None
        if not title_s and not desc_s:
            continue
        rows.append((int(idx), title_s or None, desc_s or None))
    return rows[:sample_size]


def _load_sample_from_bigquery(
    sample_size: int,
    project: str,
    dataset_id: str,
    table_id: str = "raw_kaggle_data_engineer_2023",
) -> list[tuple[int, Optional[str], Optional[str]]]:
    """Load sample (row_id, title, description) from BigQuery table."""
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    query = f"""
    SELECT job_title, job_description
    FROM `{project}.{dataset_id}.{table_id}`
    WHERE (job_title IS NOT NULL AND TRIM(job_title) != '')
       OR (job_description IS NOT NULL AND TRIM(CAST(job_description AS STRING)) != '')
    LIMIT {sample_size}
    """
    rows: list[tuple[int, Optional[str], Optional[str]]] = []
    for i, row in enumerate(client.query(query).result()):
        title = row.job_title.strip() if row.job_title and str(row.job_title).strip() else None
        desc = row.job_description.strip() if row.job_description and str(row.job_description).strip() else None
        if not title and not desc:
            continue
        rows.append((i, title, desc))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare taxonomy vs LLM skills extraction on Kaggle DE sample.",
    )
    parser.add_argument("--sample", type=int, default=300, help="Max number of rows to sample (default 300)")
    parser.add_argument("--output", default="comparison_skills.csv", help="Output CSV path (default comparison_skills.csv)")
    parser.add_argument(
        "--from-bigquery",
        action="store_true",
        help="Read sample from BigQuery raw_kaggle_data_engineer_2023 instead of CSV",
    )
    parser.add_argument("--print-metrics", action="store_true", help="Print summary metrics after writing CSV")
    parser.add_argument("--llm-batch-size", type=int, default=10, help="Batch size for LLM calls (default 10)")
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM extraction (taxonomy only); no API key needed")
    args = parser.parse_args()

    if args.from_bigquery:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT", "").strip()
        dataset_id = os.environ.get("BIGQUERY_DATASET", "job_market_analysis").strip()
        if not project:
            logger.error("GOOGLE_CLOUD_PROJECT or GCP_PROJECT required for --from-bigquery")
            return 1
        logger.info("Loading sample of %d rows from BigQuery %s.%s", args.sample, dataset_id, "raw_kaggle_data_engineer_2023")
        sample_rows = _load_sample_from_bigquery(args.sample, project, dataset_id)
    else:
        logger.info("Loading sample of %d rows from Kaggle DE CSV", args.sample)
        sample_rows = _load_sample_from_csv(args.sample)

    if not sample_rows:
        logger.error("No rows to compare")
        return 1

    logger.info("Running taxonomy extraction on %d rows ...", len(sample_rows))
    from ingestion.skills_extraction import extract_skills_taxonomy, extract_skills_llm_batch

    taxonomy_results = [extract_skills_taxonomy(title, desc) for _, title, desc in sample_rows]

    if args.skip_llm:
        logger.info("Skipping LLM extraction (--skip-llm). skills_llm will be empty.")
        llm_results = [[] for _ in sample_rows]
    else:
        logger.info("Running LLM (batch) extraction on %d rows ...", len(sample_rows))
        row_pairs = [(title, desc) for _, title, desc in sample_rows]
        llm_results = extract_skills_llm_batch(row_pairs, batch_size=args.llm_batch_size)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    snippet_len = 200

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "row_id", "job_title", "description_snippet", "skills_taxonomy", "skills_llm", "jaccard_similarity",
        ])
        for (row_id, title, desc), skills_tax, skills_llm in zip(sample_rows, taxonomy_results, llm_results):
            desc_snippet = (desc or "")[:snippet_len]
            if desc and len(desc) > snippet_len:
                desc_snippet += "..."
            jaccard = _jaccard(skills_tax, skills_llm)
            writer.writerow([
                row_id,
                title or "",
                desc_snippet,
                "|".join(skills_tax) if skills_tax else "",
                "|".join(skills_llm) if skills_llm else "",
                f"{jaccard:.4f}",
            ])

    logger.info("Wrote %d rows to %s", len(sample_rows), out_path)

    if args.print_metrics:
        _print_metrics(out_path, len(sample_rows), skip_llm=args.skip_llm)

    return 0


def _print_metrics(csv_path: Path, n_rows: int, skip_llm: bool = False) -> None:
    """Read comparison CSV and print summary metrics."""
    import csv as csv_module
    jaccards: list[float] = []
    tax_nonempty = 0
    llm_nonempty = 0
    tax_sizes: list[int] = []
    llm_sizes: list[int] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv_module.DictReader(f)
        for row in reader:
            j = row.get("jaccard_similarity", "")
            if j:
                try:
                    jaccards.append(float(j))
                except ValueError:
                    pass
            tax = (row.get("skills_taxonomy") or "").strip()
            llm = (row.get("skills_llm") or "").strip()
            if tax:
                tax_nonempty += 1
                tax_sizes.append(len(tax.split("|")))
            if llm:
                llm_nonempty += 1
                llm_sizes.append(len(llm.split("|")))
    print("\n--- Skills extraction comparison metrics ---")
    print(f"Rows: {n_rows}")
    if jaccards:
        print(f"Mean Jaccard similarity (taxonomy vs LLM): {sum(jaccards) / len(jaccards):.4f}")
    print(f"Rows with taxonomy skills non-empty: {tax_nonempty} ({100 * tax_nonempty / n_rows:.1f}%)")
    print(f"Rows with LLM skills non-empty: {llm_nonempty} ({100 * llm_nonempty / n_rows:.1f}%)" + (" (LLM skipped with --skip-llm)" if skip_llm else ""))
    if tax_sizes:
        print(f"Mean skills per row (taxonomy): {sum(tax_sizes) / len(tax_sizes):.2f}")
    if llm_sizes:
        print(f"Mean skills per row (LLM): {sum(llm_sizes) / len(llm_sizes):.2f}")
    if skip_llm:
        print("To compare with Gemini: set GOOGLE_API_KEY and run without --skip-llm.")
    print("--- Review comparison_skills.csv and choose taxonomy / LLM / hybrid (see docs/EVALUATE_SKILLS_EXTRACTION.md) ---\n")


if __name__ == "__main__":
    sys.exit(main())
