"""dlt pipeline: Jobven (last 24h, US) → GCS (Parquet). Free tier: 10/page, 300 calls/month."""
from ingestion.pipelines.common import run_pipeline
from ingestion.sources.jobven_jobs import stream_jobven_jobs

PIPELINE_NAME = "horizon_jobven_jobs"
DATASET_NAME = "jobven_jobs"


def run():
    return run_pipeline(PIPELINE_NAME, DATASET_NAME, stream_jobven_jobs)
