"""dlt pipeline: Hugging Face data_jobs → GCS (Parquet), full replace."""
import logging
import os
from typing import Iterator

import dlt

from ingestion.config import get_gcs_base_url
from ingestion.sources.huggingface_data_jobs import stream_huggingface_data_jobs

logger = logging.getLogger(__name__)

PIPELINE_NAME = "horizon_huggingface_data_jobs"
TABLE_NAME = "jobs"
DATASET_NAME = "huggingface_data_jobs"


def _jobs_resource() -> Iterator[dict]:
    """dlt resource: yields one row per call from HF stream batches."""
    for batch in stream_huggingface_data_jobs():
        for row in batch:
            yield row


def run() -> dlt.Pipeline:
    """Run Hugging Face → GCS pipeline (full replace). Uses ADC for GCS."""
    bucket_base = get_gcs_base_url()
    bucket_url = f"{bucket_base.rstrip('/')}/{DATASET_NAME}"
    os.environ["DESTINATION__FILESYSTEM__BUCKET_URL"] = bucket_url

    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination="filesystem",
        dataset_name=DATASET_NAME,
    )
    load_info = pipeline.run(
        _jobs_resource(),
        table_name=TABLE_NAME,
        write_disposition="replace",
        loader_file_format="parquet",
    )
    logger.info("Hugging Face pipeline load_info: %s", load_info)
    return pipeline
