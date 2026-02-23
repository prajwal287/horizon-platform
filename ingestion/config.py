"""Ingestion config: GCS bucket, BigQuery dataset, paths, cutoff date, domain keywords."""
import os
from datetime import datetime, timezone, timedelta
from typing import List

# BigQuery: primary destination for ingestion (from Terraform: job_market_analysis)
BIGQUERY_DATASET: str = os.environ.get("BIGQUERY_DATASET", "job_market_analysis")

# GCS: required for step 1 (dlt → GCS Parquet); also used by load_gcs_to_bigquery.py
GCS_BUCKET: str = os.environ.get("GCS_BUCKET", "")
GCS_PREFIX: str = os.environ.get("GCS_PREFIX", "raw")

# Last 3 years cutoff (UTC)
CUTOFF_DATE = (datetime.now(timezone.utc) - timedelta(days=3 * 365)).date()

# Data-domain keywords for filtering (title/description/skills)
DATA_DOMAIN_KEYWORDS: List[str] = [
    "data engineer",
    "data engineering",
    "data science",
    "data scientist",
    "big data",
    "machine learning",
    "ml engineer",
    "ai ",
    "artificial intelligence",
    "analytics",
    "data analyst",
    "business intelligence",
    "bi ",
    "etl",
    "data pipeline",
    "data warehouse",
    "data lake",
]

# Hugging Face job_title_short values that are data-domain (use when present)
DATA_DOMAIN_JOB_TITLES: List[str] = [
    "Data Engineer",
    "Data Scientist",
    "Data Analyst",
    "Analytics Engineer",
    "Business Analyst",
    "Machine Learning Engineer",
]


def get_gcs_base_url() -> str:
    """Base URL for raw data in GCS (e.g. gs://bucket/raw)."""
    if not GCS_BUCKET:
        raise ValueError("GCS_BUCKET environment variable is required")
    return f"gs://{GCS_BUCKET.strip('/')}/{GCS_PREFIX.strip('/')}"


def get_bigquery_dataset() -> str:
    """BigQuery dataset for raw/silver tables (e.g. job_market_analysis)."""
    return BIGQUERY_DATASET.strip() or "job_market_analysis"
