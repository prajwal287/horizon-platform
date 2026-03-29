"""
Whitelisted BigQuery reads for data quality + agent (no arbitrary SQL from LLMs).
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

from google.cloud import bigquery
from google.cloud.exceptions import NotFound


def _project_id() -> str:
    p = (os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT", "")).strip()
    if not p:
        raise ValueError("GOOGLE_CLOUD_PROJECT (or GCP_PROJECT) is required")
    return p


def _client() -> bigquery.Client:
    return bigquery.Client(project=_project_id())


def _gold_dataset() -> str:
    """dbt-bigQuery custom schema default: {profile_dataset}_dbt_gold (override with DBT_GOLD_DATASET)."""
    env = os.environ.get("DBT_GOLD_DATASET", "").strip()
    if env:
        return env
    base = _raw_dataset()
    return f"{base}_dbt_gold"


def _raw_dataset() -> str:
    return os.environ.get("BIGQUERY_DATASET", "job_market_analysis").strip() or "job_market_analysis"


def tool_source_row_counts() -> Dict[str, Any]:
    """Row counts per source_id from gold mart (requires dbt run)."""
    project = _project_id()
    gold = _gold_dataset()
    sql = f"""
    SELECT source_id, COUNT(*) AS job_count
    FROM `{project}.{gold}.mart_jobs_curated`
    GROUP BY 1
    ORDER BY job_count DESC
    """
    try:
        rows = list(_client().query(sql).result())
    except NotFound:
        return {
            "error": f"Table {project}.{gold}.mart_jobs_curated not found. Run: cd dbt && dbt run",
            "tool": "source_row_counts",
        }
    return {
        "tool": "source_row_counts",
        "rows": [{"source_id": r["source_id"], "job_count": r["job_count"]} for r in rows],
    }


def tool_top_skills(limit: int = 15) -> Dict[str, Any]:
    """Top skills from mart_skill_demand."""
    project = _project_id()
    gold = _gold_dataset()
    lim = max(1, min(int(limit), 100))
    sql = f"""
    SELECT skill, job_postings, source_count
    FROM `{project}.{gold}.mart_skill_demand`
    ORDER BY job_postings DESC
    LIMIT {lim}
    """
    try:
        rows = list(_client().query(sql).result())
    except NotFound:
        return {"error": f"mart_skill_demand missing in {gold}. Run dbt.", "tool": "top_skills"}
    return {
        "tool": "top_skills",
        "rows": [dict(r) for r in rows],
    }


def tool_posting_volume(months: int = 6) -> Dict[str, Any]:
    """Recent monthly posting volume by source."""
    project = _project_id()
    gold = _gold_dataset()
    m = max(1, min(int(months), 36))
    sql = f"""
    SELECT source_id, posting_month, job_postings, complete_postings
    FROM `{project}.{gold}.mart_posting_volume`
    WHERE posting_month >= DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL {m} MONTH)
    ORDER BY posting_month DESC, source_id
    """
    try:
        rows = list(_client().query(sql).result())
    except NotFound:
        return {"error": f"mart_posting_volume missing in {gold}. Run dbt.", "tool": "posting_volume"}
    return {
        "tool": "posting_volume",
        "rows": [
            {
                "source_id": r["source_id"],
                "posting_month": str(r["posting_month"]) if r["posting_month"] else None,
                "job_postings": r["job_postings"],
                "complete_postings": r["complete_postings"],
            }
            for r in rows
        ],
    }


def tool_raw_table_health() -> Dict[str, Any]:
    """Row counts + max(ingested_at) for core raw tables (no dbt required)."""
    project = _project_id()
    ds = _raw_dataset()
    tables = [
        "raw_huggingface_data_jobs",
        "raw_kaggle_data_engineer_2023",
        "raw_kaggle_linkedin_postings",
        "raw_kaggle_linkedin_jobs_skills_2024",
    ]
    client = _client()
    out: List[Dict[str, Any]] = []
    for t in tables:
        fq = f"{project}.{ds}.{t}"
        sql = f"SELECT COUNT(*) AS n, MAX(ingested_at) AS last_ingested FROM `{fq}`"
        try:
            row = list(client.query(sql).result())[0]
            out.append(
                {
                    "table": t,
                    "row_count": row["n"],
                    "last_ingested": str(row["last_ingested"]) if row["last_ingested"] else None,
                }
            )
        except NotFound:
            out.append({"table": t, "row_count": None, "last_ingested": None, "error": "not_found"})
        except Exception as e:
            out.append({"table": t, "error": str(e)})
    return {"tool": "raw_table_health", "tables": out}


def _call_source_row_counts(**_: Any) -> Dict[str, Any]:
    return tool_source_row_counts()


def _call_top_skills(limit: Any = 15, **_: Any) -> Dict[str, Any]:
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = 15
    return tool_top_skills(lim)


def _call_posting_volume(months: Any = 6, **_: Any) -> Dict[str, Any]:
    try:
        m = int(months)
    except (TypeError, ValueError):
        m = 6
    return tool_posting_volume(m)


def _call_raw_table_health(**_: Any) -> Dict[str, Any]:
    return tool_raw_table_health()


TOOL_REGISTRY: Dict[str, Callable[..., Dict[str, Any]]] = {
    "source_row_counts": _call_source_row_counts,
    "top_skills": _call_top_skills,
    "posting_volume": _call_posting_volume,
    "raw_table_health": _call_raw_table_health,
}


TOOL_DESCRIPTIONS = """
- source_row_counts: No arguments. Returns job counts per source_id from dbt gold mart_jobs_curated.
- top_skills: Optional limit (integer, default 15). Top skills from mart_skill_demand.
- posting_volume: Optional months (integer, default 6). Monthly volume from mart_posting_volume.
- raw_table_health: No arguments. Row counts and last ingested_at for each raw_* table.
"""


def execute_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    arguments = arguments or {}
    if name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: {name}", "allowed": list(TOOL_REGISTRY)}
    try:
        return TOOL_REGISTRY[name](**arguments)
    except Exception as e:
        return {"error": str(e), "tool": name}
