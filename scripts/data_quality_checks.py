#!/usr/bin/env python3
"""
Post-load data quality: raw table row counts + max(ingested_at). Optional strict exit code.

Usage (from project root, ADC + env):
  python scripts/data_quality_checks.py
  python scripts/data_quality_checks.py --strict --max-age-hours 72
  python scripts/data_quality_checks.py --strict --ignore-stale   # require tables + row counts only

Stale = max(ingested_at) older than --max-age-hours unless --ignore-stale. Refresh with run_ingestion
+ load_gcs_to_bigquery, raise --max-age-hours (e.g. 168), or use --ignore-stale for “data exists” gates only.

Requires: GOOGLE_CLOUD_PROJECT, BIGQUERY_DATASET (optional).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.bq_tools import tool_raw_table_health

# Sources you may skip in BigQuery; do not fail --strict when the table is absent (same idea as dbt raw_tables_present).
_OPTIONAL_RAW = frozenset({"raw_kaggle_linkedin_postings"})


def main() -> int:
    parser = argparse.ArgumentParser(description="BigQuery raw table health checks.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any table missing, zero rows, or older than max-age-hours (when set).",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=None,
        help="If set, fail strict mode when last_ingested is older than this many hours.",
    )
    parser.add_argument(
        "--ignore-stale",
        action="store_true",
        help="With --strict, skip freshness (max-age) failures; still enforce present tables and row counts.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    args = parser.parse_args()

    result = tool_raw_table_health()
    tables = result.get("tables", [])

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Data quality — raw tables")
        for t in tables:
            print(f"  {t.get('table')}: rows={t.get('row_count')} last={t.get('last_ingested')} err={t.get('error')}")

    if not args.strict:
        return 0

    now = datetime.now(timezone.utc)
    failures: list[str] = []
    for t in tables:
        name = t.get("table", "?")
        if t.get("error") == "not_found":
            if name in _OPTIONAL_RAW:
                print(f"  (strict) optional table missing — ignored: {name}", file=sys.stderr)
                continue
            failures.append(f"{name}: table missing")
            continue
        if t.get("error"):
            failures.append(f"{name}: {t.get('error')}")
            continue
        n = t.get("row_count")
        if n is None or n == 0:
            failures.append(f"{name}: zero or unknown rows")
        if (
            args.max_age_hours
            and not args.ignore_stale
            and t.get("last_ingested")
        ):
            try:
                # BigQuery TIMESTAMP string often ISO-like
                raw = str(t["last_ingested"]).replace("Z", "+00:00")
                if raw.endswith("+00:00") or raw.endswith("UTC"):
                    last = datetime.fromisoformat(raw.replace("UTC", "+00:00"))
                else:
                    last = datetime.fromisoformat(raw)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                age_h = (now - last).total_seconds() / 3600.0
                if age_h > args.max_age_hours:
                    failures.append(f"{name}: stale ({age_h:.1f}h > {args.max_age_hours}h)")
            except Exception:
                failures.append(f"{name}: could not parse last_ingested")

    if failures:
        print("STRICT failures:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
