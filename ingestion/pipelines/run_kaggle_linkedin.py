"""dlt pipeline: Kaggle linkedin-job-postings → GCS (Parquet). Step 1 of dlt → GCS → BigQuery."""
from ingestion.pipelines.common import run_pipeline
from ingestion.sources.kaggle_linkedin_postings import stream_kaggle_linkedin_postings

PIPELINE_NAME = "horizon_kaggle_linkedin_postings"
DATASET_NAME = "kaggle_linkedin_postings"


def run():
    return run_pipeline(PIPELINE_NAME, DATASET_NAME, stream_kaggle_linkedin_postings)
