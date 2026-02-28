"""dlt pipeline: Hugging Face data_jobs → GCS (Parquet). Step 1 of dlt → GCS → BigQuery."""
from ingestion.pipelines.common import run_pipeline
from ingestion.sources.huggingface_data_jobs import stream_huggingface_data_jobs

PIPELINE_NAME = "horizon_huggingface_data_jobs"
DATASET_NAME = "huggingface_data_jobs"


def run():
    return run_pipeline(PIPELINE_NAME, DATASET_NAME, stream_huggingface_data_jobs)
