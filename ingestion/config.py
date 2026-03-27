"""
Config from env: GCS bucket, BigQuery dataset, paths. Also: cutoff date, domain keywords, and skills taxonomy for extraction.
"""
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional

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

# Curated data-engineering skills for taxonomy-based extraction (Kaggle DE and similar).
# Order: longer phrases first so "google cloud" matches before "cloud".
# Aliases map variant -> canonical name (e.g. "pyspark" -> "Spark").
DATA_ENGINEER_SKILLS: List[str] = [
    "apache spark",
    "apache kafka",
    "apache airflow",
    "google cloud",
    "google cloud platform",
    "machine learning",
    "data pipeline",
    "data warehouse",
    "data lake",
    "data modeling",
    "etl",
    "elt",
    "python",
    "python3",
    "sql",
    "spark",
    "pyspark",
    "kafka",
    "airflow",
    "aws",
    "gcp",
    "azure",
    "snowflake",
    "redshift",
    "bigquery",
    "databricks",
    "dbt",
    "terraform",
    "docker",
    "kubernetes",
    "k8s",
    "java",
    "scala",
    "pandas",
    "numpy",
    "tableau",
    "looker",
    "power bi",
    "dbt core",
    "fivetran",
    "talend",
    "informatica",
    "postgresql",
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "elasticsearch",
    "hadoop",
    "hive",
    "presto",
    "trino",
    "beam",
    "dataflow",
    "cloud storage",
    "pub/sub",
    "bigtable",
    "firestore",
    "dataform",
    "dbt cloud",
    "great expectations",
    "dagster",
    "prefect",
]

# Aliases: text that matches in description -> canonical skill name for output.
# Keys are lowercase; values are the canonical label to emit.
DATA_ENGINEER_SKILL_ALIASES: dict[str, str] = {
    "pyspark": "Spark",
    "apache spark": "Spark",
    "spark": "Spark",
    "apache kafka": "Kafka",
    "kafka": "Kafka",
    "apache airflow": "Airflow",
    "airflow": "Airflow",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "gcp": "GCP",
    "aws": "AWS",
    "azure": "Azure",
    "snowflake": "Snowflake",
    "redshift": "Redshift",
    "bigquery": "BigQuery",
    "databricks": "Databricks",
    "dbt": "dbt",
    "dbt core": "dbt",
    "dbt cloud": "dbt",
    "terraform": "Terraform",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "python": "Python",
    "python3": "Python",
    "sql": "SQL",
    "java": "Java",
    "scala": "Scala",
    "etl": "ETL",
    "elt": "ELT",
    "machine learning": "Machine Learning",
    "data pipeline": "Data Pipeline",
    "data warehouse": "Data Warehouse",
    "data lake": "Data Lake",
    "data modeling": "Data Modeling",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "tableau": "Tableau",
    "looker": "Looker",
    "power bi": "Power BI",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "hadoop": "Hadoop",
    "hive": "Hive",
    "presto": "Presto",
    "trino": "Trino",
    "beam": "Beam",
    "dataflow": "Dataflow",
    "fivetran": "Fivetran",
    "talend": "Talend",
    "informatica": "Informatica",
    "great expectations": "Great Expectations",
    "dagster": "Dagster",
    "prefect": "Prefect",
}


def normalize_gcs_bucket(raw: str) -> str:
    """Strip whitespace; if user set gs://bucket/..., keep only the bucket segment."""
    b = (raw or "").strip()
    if b.lower().startswith("gs://"):
        b = b[5:].strip().split("/")[0].strip()
    return b


def gcs_bucket_config_error(bucket: str) -> Optional[str]:
    """
    Return a human-readable error if GCS_BUCKET looks like Terraform stderr (common when
    `terraform output` is run with no state / wrong directory) instead of a real bucket name.
    """
    if not bucket:
        return "GCS_BUCKET is empty. Set it in .env (single line, no quotes) or export it."
    if any(ch in bucket for ch in ("\n", "\r", "\t")):
        return (
            "GCS_BUCKET contains line breaks — often a Terraform error block was pasted into .env. "
            "Fix: cd terraform && terraform output -raw gcs_bucket_name"
        )
    if any(s in bucket for s in ("│", "╷", "╵")) or "No outputs found" in bucket or (
        "Warning" in bucket and "output" in bucket.lower()
    ):
        return (
            "GCS_BUCKET is not a bucket name (looks like Terraform warning text). "
            "Run from the repo: cd terraform && terraform output -raw gcs_bucket_name "
            "after a successful terraform apply, then set GCS_BUCKET to that value only."
        )
    if len(bucket) < 3 or len(bucket) > 222:
        return f"GCS_BUCKET length ({len(bucket)}) is not a valid GCS bucket name."
    # Terraform: google_storage_bucket.raw.name = "${var.project_id}-${var.gcs_bucket_name}" (suffix alone is wrong).
    if bucket == "job-lakehouse-raw":
        return (
            'GCS_BUCKET is the Terraform *suffix* only (job-lakehouse-raw), not the actual bucket. '
            "The bucket created by this repo is \"<GOOGLE_CLOUD_PROJECT>-job-lakehouse-raw\". "
            "Fix: export GCS_BUCKET=$(terraform -chdir=terraform output -raw gcs_bucket_name)"
        )
    return None


def get_gcs_base_url() -> str:
    """Base URL for raw data in GCS (e.g. gs://bucket/raw)."""
    bucket = normalize_gcs_bucket(GCS_BUCKET)
    err = gcs_bucket_config_error(bucket)
    if err:
        raise ValueError(err)
    return f"gs://{bucket.strip('/')}/{GCS_PREFIX.strip('/')}"


def get_bigquery_dataset() -> str:
    """BigQuery dataset for raw/silver tables (e.g. job_market_analysis)."""
    return BIGQUERY_DATASET.strip() or "job_market_analysis"
