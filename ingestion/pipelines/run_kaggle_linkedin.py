"""dlt pipeline: Kaggle linkedin-job-postings → GCS (Parquet), full replace."""
import logging
import os
from typing import Iterator

import dlt

from ingestion.config import get_gcs_base_url
from ingestion.sources.kaggle_linkedin_postings import stream_kaggle_linkedin_postings

logger = logging.getLogger(__name__)

PIPELINE_NAME = "horizon_kaggle_linkedin_postings"
TABLE_NAME = "jobs"
DATASET_NAME = "kaggle_linkedin_postings"


def _jobs_resource() -> Iterator[dict]:
    for batch in stream_kaggle_linkedin_postings():
        for row in batch:
            yield row


def run() -> dlt.Pipeline:
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
    logger.info("Kaggle linkedin_postings pipeline load_info: %s", load_info)
    return pipeline
