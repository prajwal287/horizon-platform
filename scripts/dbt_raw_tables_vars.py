#!/usr/bin/env python3
"""
List raw_* base tables in the Horizon BigQuery dataset and emit dbt vars JSON.

adapter.get_relation() does not see tables during dbt's parse phase, so optional
bronze/stg use var('raw_tables_present') instead. This script sets that list from
what actually exists in BigQuery.

Usage (from repo root, with ADC and .env):
  dbt run --vars "$(python scripts/dbt_raw_tables_vars.py --json)"

Or print a copy-paste command:
  python scripts/dbt_raw_tables_vars.py --print-dbt-run
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Must match dbt sources / bronze models
KNOWN_RAW_TABLES: tuple[str, ...] = (
    "raw_huggingface_data_jobs",
    "raw_kaggle_data_engineer_2023",
    "raw_kaggle_linkedin_postings",
    "raw_kaggle_linkedin_jobs_skills_2024",
)


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env, override=False)
    except ImportError:
        with open(env) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and v:
                        os.environ.setdefault(k, v)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit dbt raw_tables_present vars from BigQuery.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print single-line JSON for dbt --vars (use in shell subsitution).",
    )
    parser.add_argument(
        "--print-dbt-run",
        action="store_true",
        help="Print a suggested dbt run command (run from dbt/ directory).",
    )
    args = parser.parse_args()

    _load_dotenv()
    project = (os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or "").strip()
    dataset = (
        os.environ.get("BIGQUERY_DATASET", "job_market_analysis").strip() or "job_market_analysis"
    )

    if not project:
        print("GOOGLE_CLOUD_PROJECT or GCP_PROJECT is required.", file=sys.stderr)
        return 1

    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    q = f"""
    SELECT table_name
    FROM `{project}.{dataset}.INFORMATION_SCHEMA.TABLES`
    WHERE table_type IN ('BASE TABLE', 'EXTERNAL')
      AND STARTS_WITH(table_name, 'raw_')
    """
    names = {r["table_name"] for r in client.query(q).result()}
    present = [t for t in KNOWN_RAW_TABLES if t in names]

    payload = {"raw_tables_present": present}

    if args.json:
        print(json.dumps(payload, separators=(",", ":")))
        return 0

    if args.print_dbt_run:
        quoted = json.dumps(payload)
        print("From repo root (script resolves .env + queries BigQuery):")
        print(f"  cd dbt && dbt run --vars {shlex.quote(quoted)}")
        return 0

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
