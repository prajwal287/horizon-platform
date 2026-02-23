#!/usr/bin/env python3
"""
Step 2 of dlt → GCS → BigQuery: load Parquet files from GCS into BigQuery tables.

Run after run_ingestion.py (which writes Parquet to GCS). Requires GCS_BUCKET, GOOGLE_CLOUD_PROJECT, BIGQUERY_DATASET.

Usage:
  python scripts/load_gcs_to_bigquery.py --source all
  python scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer

From project root or /app in Docker:
  docker compose run --rm app python scripts/load_gcs_to_bigquery.py --source all
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Source slug (CLI) -> (GCS path suffix under raw/, BigQuery table name)
SOURCE_TO_GCS_AND_TABLE = {
    "huggingface": ("huggingface_data_jobs", "raw_huggingface_data_jobs"),
    "kaggle_data_engineer": ("kaggle_data_engineer_2023", "raw_kaggle_data_engineer_2023"),
    "kaggle_linkedin": ("kaggle_linkedin_postings", "raw_kaggle_linkedin_postings"),
    "kaggle_linkedin_skills": ("kaggle_linkedin_jobs_skills_2024", "raw_kaggle_linkedin_jobs_skills_2024"),
}


def load_source(bucket: str, prefix: str, project: str, dataset_id: str, table_id: str) -> None:
    """Load all Parquet files under gs://bucket/prefix/ into BigQuery dataset.table (WRITE_TRUNCATE)."""
    import gcsfs
    from google.cloud import bigquery

    fs = gcsfs.GCSFileSystem()
    path = f"gs://{bucket}/{prefix.rstrip('/')}/**/*.parquet"
    uris = fs.glob(path)
    if not uris:
        logger.warning("No Parquet files under gs://%s/%s", bucket, prefix)
        return
    client_bq = bigquery.Client(project=project)
    table_ref = f"{project}.{dataset_id}.{table_id}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )
    load_job = client_bq.load_table_from_uri(uris, table_ref, job_config=job_config)
    load_job.result()
    table = client_bq.get_table(table_ref)
    logger.info("Loaded %d rows into %s from %d Parquet file(s)", table.num_rows, table_ref, len(uris))


def main() -> int:
    parser = argparse.ArgumentParser(description="Load GCS Parquet → BigQuery (step 2 after dlt → GCS).")
    parser.add_argument(
        "--source",
        choices=["all"] + list(SOURCE_TO_GCS_AND_TABLE),
        default="all",
        help="Which source(s) to load. Default: all.",
    )
    args = parser.parse_args()

    bucket = os.environ.get("GCS_BUCKET", "").strip()
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT", "").strip()
    dataset_id = os.environ.get("BIGQUERY_DATASET", "job_market_analysis").strip() or "job_market_analysis"

    if not bucket:
        logger.error("GCS_BUCKET is required. Set it in .env or export.")
        return 1
    if not project:
        logger.error("GOOGLE_CLOUD_PROJECT (or GCP_PROJECT) is required.")
        return 1

    if args.source == "all":
        to_load = list(SOURCE_TO_GCS_AND_TABLE.items())
    else:
        to_load = [(args.source, SOURCE_TO_GCS_AND_TABLE[args.source])]

    for source_slug, (gcs_suffix, bq_table) in to_load:
        prefix = f"raw/{gcs_suffix}/"
        logger.info("Loading gs://%s/%s → %s.%s", bucket, prefix, dataset_id, bq_table)
        try:
            load_source(bucket, prefix, project, dataset_id, bq_table)
        except Exception as e:
            logger.exception("Load failed for %s: %s", source_slug, e)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
