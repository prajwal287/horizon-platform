#!/usr/bin/env python3
"""
Create or refresh the BigQuery master_jobs view/table (union of all raw job tables).

Requires GOOGLE_CLOUD_PROJECT (or GCP_PROJECT) and BIGQUERY_DATASET. Run after load_gcs_to_bigquery.py.
SQL union is read from scripts/sql/master_jobs_view.sql (single source of truth).

Usage:
  python scripts/create_master_table.py [--materialize]
  --materialize: create/refresh a table instead of a view (TRUNCATE + INSERT).
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_SQL_DIR = Path(__file__).resolve().parent / "sql"


def _load_union_sql(project: str, dataset: str) -> str:
    path = _SQL_DIR / "master_jobs_view.sql"
    text = path.read_text().strip()
    return text.format(project=project, dataset=dataset)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or refresh BigQuery master_jobs view/table.")
    parser.add_argument(
        "--materialize",
        action="store_true",
        help="Create/refresh a materialized table (table must exist; use --create-table once to create it)",
    )
    parser.add_argument(
        "--create-table",
        action="store_true",
        help="Create the master_jobs table (empty) then exit; use with --materialize to populate later",
    )
    args = parser.parse_args()

    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT", "").strip()
    dataset_id = os.environ.get("BIGQUERY_DATASET", "job_market_analysis").strip() or "job_market_analysis"

    if not project:
        logger.error("GOOGLE_CLOUD_PROJECT or GCP_PROJECT is required.")
        return 1

    from google.cloud import bigquery
    client = bigquery.Client(project=project)
    ref = f"{project}.{dataset_id}.master_jobs"

    if args.create_table:
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS `{ref}` AS
        SELECT * FROM `{project}.{dataset_id}.raw_huggingface_data_jobs` LIMIT 0
        """
        client.query(create_sql).result()
        logger.info("Created table (if not exists) %s", ref)
        return 0

    union_sql = _load_union_sql(project, dataset_id)

    if args.materialize:
        materialize_sql = f"TRUNCATE TABLE `{ref}`;\nINSERT INTO `{ref}`\n{union_sql}"
        try:
            client.query(materialize_sql).result()
            logger.info("Refreshed materialized table %s", ref)
        except Exception as e:
            if "Not found" in str(e) or "404" in str(e):
                logger.error("Table %s does not exist. Run with --create-table first.", ref)
            else:
                raise
    else:
        view_sql = f"CREATE OR REPLACE VIEW `{ref}` AS\n{union_sql}"
        client.query(view_sql).result()
        logger.info("Created/updated view %s", ref)

    return 0


if __name__ == "__main__":
    sys.exit(main())
