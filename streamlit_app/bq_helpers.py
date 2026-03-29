"""BigQuery helpers for the Streamlit app — parameterized whitelist-safe table names."""
from __future__ import annotations

import re
from typing import Any, Optional, Sequence

from google.cloud import bigquery
from google.cloud.exceptions import NotFound

_RAW_PATTERN = re.compile(r"^raw_[a-z0-9_]+$")


def sort_source_ids_huggingface_first(source_ids: list[str]) -> list[str]:
    """List unique source_ids with Hugging Face sources first, then others A–Z."""
    seen: set[str] = set()
    ordered: list[str] = []
    for s in source_ids:
        if s and s not in seen:
            seen.add(s)
            ordered.append(s)
    hf = [x for x in ordered if "huggingface" in x.lower()]
    rest = sorted([x for x in ordered if "huggingface" not in x.lower()])
    return sorted(hf) + rest


def get_project_id() -> str:
    import os

    return (os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or "").strip()


def get_dataset_id() -> str:
    import os

    return (os.environ.get("BIGQUERY_DATASET", "job_market_analysis") or "job_market_analysis").strip()


def bq_client(project_id: str) -> bigquery.Client:
    return bigquery.Client(project=project_id)


def table_exists(client: bigquery.Client, project: str, dataset: str, table: str) -> bool:
    try:
        client.get_table(f"{project}.{dataset}.{table}")
        return True
    except NotFound:
        return False


def list_raw_tables(client: bigquery.Client, project: str, dataset: str) -> list[str]:
    """Table IDs in dataset matching raw_* (Horizon raw landing tables)."""
    ref = f"{project}.{dataset}"
    out: list[str] = []
    for t in client.list_tables(ref):
        tid = t.table_id
        if _RAW_PATTERN.match(tid):
            out.append(tid)
    return sorted(out)


def resolve_jobs_relation(client: bigquery.Client, project: str, dataset: str) -> tuple[str, str]:
    """
    Return (fully_qualified_table_id, mode).
    mode is 'master_jobs' | 'raw_single' and for raw_single the FQN is the selected raw table.
    """
    if table_exists(client, project, dataset, "master_jobs"):
        return f"`{project}.{dataset}.master_jobs`", "master_jobs"
    raw = list_raw_tables(client, project, dataset)
    if not raw:
        raise RuntimeError(
            f"No `master_jobs` view and no raw_* tables in {project}.{dataset}. "
            "Run load_gcs_to_bigquery.py (and optionally create_master_table.py)."
        )
    if len(raw) == 1:
        return f"`{project}.{dataset}.{raw[0]}`", "raw_single"
    return "", "raw_pick"


def qualifying_raw_table(project: str, dataset: str, table_id: str) -> str:
    if not _RAW_PATTERN.match(table_id):
        raise ValueError("Invalid table id")
    return f"`{project}.{dataset}.{table_id}`"


def run_query(
    client: bigquery.Client,
    sql: str,
    params: Optional[Sequence[bigquery.ScalarQueryParameter | bigquery.ArrayQueryParameter]] = None,
) -> list[dict[str, Any]]:
    job_config = bigquery.QueryJobConfig(query_parameters=list(params or []))
    rows = client.query(sql, job_config=job_config).result()
    return [dict(row) for row in rows]
