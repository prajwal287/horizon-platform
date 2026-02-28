"""dlt pipeline: Kaggle data-engineer-job-postings-2023 → GCS (Parquet). Step 1 of dlt → GCS → BigQuery."""
from ingestion.pipelines.common import run_pipeline
from ingestion.sources.kaggle_data_engineer_2023 import stream_kaggle_data_engineer_2023

PIPELINE_NAME = "horizon_kaggle_data_engineer_2023"
DATASET_NAME = "kaggle_data_engineer_2023"


def run():
    return run_pipeline(PIPELINE_NAME, DATASET_NAME, stream_kaggle_data_engineer_2023)
