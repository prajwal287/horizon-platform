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


def get_gcs_base_url() -> str:
    """Base URL for raw data in GCS (e.g. gs://bucket/raw)."""
    if not GCS_BUCKET:
        raise ValueError("GCS_BUCKET environment variable is required")
    return f"gs://{GCS_BUCKET.strip('/')}/{GCS_PREFIX.strip('/')}"


def get_bigquery_dataset() -> str:
    """BigQuery dataset for raw/silver tables (e.g. job_market_analysis)."""
    return BIGQUERY_DATASET.strip() or "job_market_analysis"
