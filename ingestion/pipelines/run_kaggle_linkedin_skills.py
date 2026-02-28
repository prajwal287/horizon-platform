"""dlt pipeline: Kaggle linkedin-jobs-and-skills-2024 → GCS (Parquet). Step 1 of dlt → GCS → BigQuery."""
from ingestion.pipelines.common import run_pipeline
from ingestion.sources.kaggle_linkedin_jobs_skills_2024 import stream_kaggle_linkedin_jobs_skills_2024

PIPELINE_NAME = "horizon_kaggle_linkedin_jobs_skills_2024"
DATASET_NAME = "kaggle_linkedin_jobs_skills_2024"


def run():
    return run_pipeline(PIPELINE_NAME, DATASET_NAME, stream_kaggle_linkedin_jobs_skills_2024)
