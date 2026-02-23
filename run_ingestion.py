#!/usr/bin/env python3
"""
Horizon ingestion CLI: run one or all dlt pipelines (Hugging Face + Kaggle → GCS Parquet). Step 1 of dlt → GCS → BigQuery.

Usage:
  python run_ingestion.py --source all
  python run_ingestion.py --source huggingface
  python run_ingestion.py --source kaggle_data_engineer
  python run_ingestion.py --source kaggle_linkedin
  python run_ingestion.py --source kaggle_linkedin_skills

Requires GCS_BUCKET and GOOGLE_CLOUD_PROJECT (or GCP_PROJECT). Step 2: run scripts/load_gcs_to_bigquery.py to load GCS Parquet → BigQuery.
For Kaggle sources, KAGGLE_USERNAME and KAGGLE_API_TOKEN (or KAGGLE_KEY) are required.
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SOURCES = [
    "huggingface",
    "kaggle_data_engineer",
    "kaggle_linkedin",
    "kaggle_linkedin_skills",
]


def run_huggingface() -> None:
    from ingestion.pipelines.run_huggingface import run
    run()


def run_kaggle_data_engineer() -> None:
    from ingestion.pipelines.run_kaggle_data_engineer import run
    run()


def run_kaggle_linkedin() -> None:
    from ingestion.pipelines.run_kaggle_linkedin import run
    run()


def run_kaggle_linkedin_skills() -> None:
    from ingestion.pipelines.run_kaggle_linkedin_skills import run
    run()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Horizon ingestion pipelines (dlt → GCS Parquet). Step 2: load_gcs_to_bigquery.py.",
    )
    parser.add_argument(
        "--source",
        choices=["all"] + SOURCES,
        default="all",
        help="Which source(s) to run. Default: all.",
    )
    args = parser.parse_args()

    import os
    if not os.environ.get("GCS_BUCKET"):
        logger.error("GCS_BUCKET is required for dlt → GCS. Set it or use .env (see .env.example).")
        return 1
    if not (os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")):
        logger.error("GOOGLE_CLOUD_PROJECT (or GCP_PROJECT) is required. Set it or use .env.")
        return 1

    if args.source == "all":
        to_run = SOURCES
    else:
        to_run = [args.source]

    runners = {
        "huggingface": run_huggingface,
        "kaggle_data_engineer": run_kaggle_data_engineer,
        "kaggle_linkedin": run_kaggle_linkedin,
        "kaggle_linkedin_skills": run_kaggle_linkedin_skills,
    }

    for name in to_run:
        logger.info("Starting pipeline: %s", name)
        try:
            runners[name]()
            logger.info("Completed pipeline: %s", name)
        except Exception as e:
            logger.exception("Pipeline %s failed: %s", name, e)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
