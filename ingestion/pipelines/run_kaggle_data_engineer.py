"""dlt pipeline: Kaggle data-engineer-job-postings-2023 → GCS (Parquet), full replace. Step 1 of dlt → GCS → BigQuery."""
import logging
import os
from typing import Iterator

import dlt

from ingestion.config import get_gcs_base_url
from ingestion.sources.kaggle_data_engineer_2023 import stream_kaggle_data_engineer_2023

logger = logging.getLogger(__name__)

PIPELINE_NAME = "horizon_kaggle_data_engineer_2023"
TABLE_NAME = "jobs"
DATASET_NAME = "kaggle_data_engineer_2023"

JOBS_COLUMNS = {
    "source_id": {"data_type": "text"},
    "source_name": {"data_type": "text"},
    "job_title": {"data_type": "text"},
    "job_description": {"data_type": "text"},
    "company_name": {"data_type": "text"},
    "location": {"data_type": "text"},
    "posted_date": {"data_type": "date"},
    "job_url": {"data_type": "text"},
    "skills": {"data_type": "json"},
    "salary_info": {"data_type": "text"},
    "ingested_at": {"data_type": "timestamp"},
}


@dlt.resource(name=TABLE_NAME, write_disposition="replace", columns=JOBS_COLUMNS)
def jobs_resource() -> Iterator[dict]:
    for batch in stream_kaggle_data_engineer_2023():
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
    load_info = pipeline.run(jobs_resource(), loader_file_format="parquet")
    logger.info("Kaggle data_engineer_2023 pipeline load_info: %s", load_info)
    return pipeline
