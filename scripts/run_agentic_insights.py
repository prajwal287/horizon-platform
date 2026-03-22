#!/usr/bin/env python3
"""
Agentic analytics: Gemini picks a whitelisted BigQuery tool, runs it, summarizes results.

Requires: GOOGLE_CLOUD_PROJECT, GOOGLE_API_KEY (or GEMINI_API_KEY), ADC for BigQuery.
Optional: DBT_GOLD_DATASET (default dbt_gold) after `dbt run`.

Usage:
  python scripts/run_agentic_insights.py "What are the top data skills in our mart?"
  python scripts/run_agentic_insights.py --raw-only "Are raw tables loaded?"
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Agentic job-market insights (Gemini + safe BQ tools).")
    parser.add_argument("question", nargs="?", default="Summarize row counts per source in the gold mart.")
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="Skip LLM; only print raw_table_health JSON.",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.0-flash",
        help="Gemini model id (default: gemini-2.0-flash).",
    )
    parser.add_argument("--no-summary", action="store_true", help="Print tool JSON only (second LLM call skipped).")
    args = parser.parse_args()

    from agents.bq_tools import tool_raw_table_health
    from agents.agentic_runner import run_agentic_turn

    if args.raw_only:
        import json

        print(json.dumps(tool_raw_table_health(), indent=2, default=str))
        return 0

    try:
        out = run_agentic_turn(
            args.question,
            model_name=args.model,
            summarize=not args.no_summary,
        )
    except Exception as e:
        logging.exception("Agent run failed: %s", e)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
