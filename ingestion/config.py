"""Ingestion config: GCS bucket, paths, cutoff date, domain keywords."""
import os
from datetime import datetime, timezone, timedelta
from typing import List

# Required: set by Docker or env
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
