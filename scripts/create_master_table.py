#!/usr/bin/env python3
"""
Build BigQuery master_jobs = union of all raw_* tables that exist. Run after load_gcs_to_bigquery.py.

Flow: List raw tables in dataset → build UNION SQL (simple or clean with is_complete) → CREATE VIEW or TABLE.
Uses only tables that exist (no error if some sources were not loaded).

Usage:
  python scripts/create_master_table.py [--clean]              # view (clean = consistent types + is_complete)
  python scripts/create_master_table.py --clean --create-table  # create empty table
  python scripts/create_master_table.py --clean --materialize   # refresh table

Requires: GOOGLE_CLOUD_PROJECT (or GCP_PROJECT), BIGQUERY_DATASET.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.raw_table_names import RAW_TABLE_IDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# One branch of the clean union (same SELECT for each table).
_CLEAN_SELECT = """
    CAST(source_id AS STRING)       AS source_id,
    CAST(source_name AS STRING)     AS source_name,
    CAST(job_title AS STRING)       AS job_title,
    CAST(job_description AS STRING) AS job_description,
    CAST(company_name AS STRING)    AS company_name,
    CAST(location AS STRING)        AS location,
    CAST(posted_date AS DATE)       AS posted_date,
    CAST(job_url AS STRING)         AS job_url,
    skills,
    CAST(COALESCE(salary_info, '') AS STRING) AS salary_info,
    CAST(ingested_at AS TIMESTAMP)  AS ingested_at"""


def _existing_raw_tables(client, project: str, dataset_id: str):
    """Return subset of _RAW_TABLES that exist in the dataset."""
    from google.cloud.bigquery import DatasetReference
    dataset_ref = DatasetReference(project, dataset_id)
    found = {t.table_id for t in client.list_tables(dataset_ref)}
    return [t for t in RAW_TABLE_IDS if t in found]


def _union_sql(project: str, dataset_id: str, table_ids: list, clean: bool) -> str:
    """Build union SQL from only the given raw table ids."""
    if not table_ids:
        return ""

    def qual(tid: str) -> str:
        return f"`{project}.{dataset_id}.{tid}`"

    if clean:
        branches = [
            f"  SELECT\n{_CLEAN_SELECT}\n  FROM {qual(t)}"
            for t in table_ids
        ]
        union_body = "\n  UNION ALL\n".join(branches)
        return f"""WITH raw_union AS (
{union_body}
)
SELECT
  *,
  (TRIM(COALESCE(job_title, '')) != ''
   AND (TRIM(COALESCE(job_description, '')) != '' OR skills IS NOT NULL)) AS is_complete
FROM raw_union"""
    else:
        return "\nUNION ALL\n".join(f"SELECT * FROM {qual(t)}" for t in table_ids)


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
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Use clean union (consistent types + is_complete flag)",
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

    existing = _existing_raw_tables(client, project, dataset_id)
    if not existing:
        logger.error(
            "No raw tables found in %s.%s. Load data first, e.g.: python3 scripts/load_gcs_to_bigquery.py --source all",
            project, dataset_id,
        )
        return 1
    missing = [t for t in RAW_TABLE_IDS if t not in existing]
    if missing:
        logger.info("Using %d raw table(s): %s (missing: %s)", len(existing), existing, missing or "none")

    if args.create_table:
        if args.clean:
            union_sql = _union_sql(project, dataset_id, existing, clean=True)
            create_sql = f"CREATE TABLE IF NOT EXISTS `{ref}` AS\n{union_sql}\nLIMIT 0"
        else:
            first_table = existing[0]
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS `{ref}` AS
            SELECT * FROM `{project}.{dataset_id}.{first_table}` LIMIT 0
            """
        client.query(create_sql).result()
        logger.info("Created table (if not exists) %s", ref)
        return 0

    union_sql = _union_sql(project, dataset_id, existing, args.clean)
    if args.clean:
        logger.info("Using clean union (consistent types + is_complete)")

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
