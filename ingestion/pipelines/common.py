"""
Shared dlt pipeline: one runner for all sources. Stream function yields batches of job dicts → dlt writes Parquet to GCS.
"""
import logging
import os
from typing import Callable, Iterator

import dlt

from ingestion.config import get_gcs_base_url
from ingestion.schema import JOBS_COLUMNS

logger = logging.getLogger(__name__)

TABLE_NAME = "jobs"


def run_pipeline(
    pipeline_name: str,
    dataset_name: str,
    stream_fn: Callable[[], Iterator[list[dict]]],
) -> dlt.Pipeline:
    """Run one dlt pipeline: stream_fn() yields batches → dlt writes Parquet to gs://bucket/raw/<dataset_name>/ (replace)."""
    bucket_base = get_gcs_base_url()
    bucket_url = f"{bucket_base.rstrip('/')}/{dataset_name}"
    os.environ["DESTINATION__FILESYSTEM__BUCKET_URL"] = bucket_url

    @dlt.resource(name=TABLE_NAME, write_disposition="replace", columns=JOBS_COLUMNS)
    def jobs_resource() -> Iterator[dict]:
        for batch in stream_fn():
            for row in batch:
                yield row

    pipeline = dlt.pipeline(
        pipeline_name=pipeline_name,
        destination="filesystem",
        dataset_name=dataset_name,
    )
    load_info = pipeline.run(jobs_resource(), loader_file_format="parquet")
    logger.info("Pipeline %s load_info: %s", pipeline_name, load_info)
    return pipeline
