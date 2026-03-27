"""
Horizon Job Lakehouse — Streamlit explorer over BigQuery (master_jobs or raw_* tables).

Run from repo root (with .env and ADC):
  streamlit run streamlit_app/app.py

Requires: GOOGLE_CLOUD_PROJECT, gcloud auth application-default login;
  BIGQUERY_DATASET (default job_market_analysis).
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _load_dotenv() -> None:
    env = _ROOT / ".env"
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
                    if k and v and k not in __import__("os").environ:
                        __import__("os").environ.setdefault(k, v)


_load_dotenv()

import pandas as pd
import streamlit as st
from google.cloud import bigquery

from streamlit_app.bq_helpers import (
    bq_client,
    get_dataset_id,
    get_project_id,
    list_raw_tables,
    qualifying_raw_table,
    resolve_jobs_relation,
    run_query,
)

st.set_page_config(
    page_title="Horizon — Job Postings",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def _client(project: str) -> bigquery.Client:
    return bq_client(project)


def main() -> None:
    st.title("Horizon job lakehouse")
    st.caption("Explore data-domain job postings loaded from Hugging Face & Kaggle (BigQuery).")

    project = get_project_id()
    dataset = get_dataset_id()

    with st.sidebar:
        st.header("Connection")
        if not project:
            st.error("Set **GOOGLE_CLOUD_PROJECT** (or **GCP_PROJECT**) in `.env` or your environment.")
            st.stop()
        st.text_input("GCP project", value=project, disabled=True)
        st.text_input("BigQuery dataset", value=dataset, disabled=True)
        st.markdown(
            "Uses **Application Default Credentials** (same as `gcloud auth application-default login`)."
        )

    client = _client(project)

    try:
        fqn, mode = resolve_jobs_relation(client, project, dataset)
    except RuntimeError as e:
        st.error(str(e))
        st.stop()

    with st.sidebar:
        st.header("Data source")
        raw_list = list_raw_tables(client, project, dataset)
        if mode == "master_jobs":
            st.success("Using unified view **`master_jobs`**")
            jobs_fqn = fqn
            source_options: list[str] | None = None
        elif mode == "raw_single":
            st.warning("No `master_jobs` view — using **`%s`**" % raw_list[0])
            jobs_fqn = fqn
            source_options = None
        else:
            st.warning("`master_jobs` not found — pick a **raw_** table to explore.")
            pick = st.selectbox("Raw table", raw_list, index=0)
            jobs_fqn = qualifying_raw_table(project, dataset, pick)
            source_options = None

        if mode == "master_jobs" and raw_list:
            counts_sql = f"""
            SELECT source_id, COUNT(*) AS n
            FROM {jobs_fqn}
            GROUP BY 1
            ORDER BY n DESC
            """
            src_rows = run_query(client, counts_sql)
            source_options = [r["source_id"] for r in src_rows if r.get("source_id")]

        st.divider()
        st.subheader("Filters")
        if source_options:
            sources_filter = st.multiselect(
                "Source",
                options=source_options,
                default=source_options,
            )
        else:
            sources_filter = []

        use_dates = st.checkbox("Filter by posted date", value=False)
        d_start = d_end = None
        if use_dates:
            col_a, col_b = st.columns(2)
            with col_a:
                d_start = st.date_input("From", value=None)
            with col_b:
                d_end = st.date_input("To", value=None)

        search = st.text_input("Search title / description", placeholder="e.g. data engineer, spark", value="")

        limit = st.slider("Rows to load", min_value=50, max_value=2000, value=200, step=50)

    # --- Overview metrics
    params: list = []
    where_parts = ["1=1"]
    if sources_filter:
        where_parts.append("source_id IN UNNEST(@sources)")
        params.append(bigquery.ArrayQueryParameter("sources", "STRING", sources_filter))
    if use_dates and d_start is not None:
        where_parts.append("posted_date >= @d0")
        params.append(bigquery.ScalarQueryParameter("d0", "DATE", d_start))
    if use_dates and d_end is not None:
        where_parts.append("posted_date <= @d1")
        params.append(bigquery.ScalarQueryParameter("d1", "DATE", d_end))
    if search.strip():
        where_parts.append(
            "LOWER(CONCAT(IFNULL(job_title,''), IFNULL(job_description,''))) LIKE @pat"
        )
        params.append(
            bigquery.ScalarQueryParameter("pat", "STRING", f"%{search.strip().lower()}%")
        )

    where_sql = " AND ".join(where_parts)

    count_sql = f"SELECT COUNT(*) AS c FROM {jobs_fqn} WHERE {where_sql}"
    total = run_query(client, count_sql, params)[0]["c"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows (filtered)", f"{total:,}")
    c2.metric("Dataset", dataset)
    if mode == "master_jobs":
        n_src = len(source_options or [])
        c3.metric("Sources in view", n_src)
    else:
        c3.metric("Mode", "single raw table")

    if mode == "master_jobs":
        try:
            meta = client.get_table(f"{project}.{dataset}.master_jobs")
            names = {f.name for f in meta.schema}
            if "is_complete" in names:
                comp_sql = f"""
                SELECT SUM(CASE WHEN is_complete THEN 1 ELSE 0 END) AS complete_rows
                FROM {jobs_fqn}
                WHERE {where_sql}
                """
                complete_n = run_query(client, comp_sql, params)[0]["complete_rows"]
                c4.metric("Complete rows (filtered)", f"{int(complete_n or 0):,}")
            else:
                c4.metric("View", "master_jobs")
        except Exception:
            c4.metric("View", "master_jobs")
    else:
        c4.metric("View", "raw table")

    tab1, tab2, tab3 = st.tabs(["By source", "Over time", "Browse jobs"])

    with tab1:
        sql_src = f"""
        SELECT source_id, COUNT(*) AS job_count
        FROM {jobs_fqn}
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY job_count DESC
        """
        rows = run_query(client, sql_src, params)
        if rows:
            df = pd.DataFrame(rows).set_index("source_id")
            st.bar_chart(df)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No rows for current filters.")

    with tab2:
        sql_time = f"""
        SELECT DATE_TRUNC(posted_date, MONTH) AS month, COUNT(*) AS job_count
        FROM {jobs_fqn}
        WHERE {where_sql}
          AND posted_date IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """
        trows = run_query(client, sql_time, params)
        if trows:
            tdf = pd.DataFrame(trows)
            tdf["month"] = pd.to_datetime(tdf["month"])
            tdf = tdf.set_index("month")
            st.line_chart(tdf)
            st.dataframe(
                pd.DataFrame(trows),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No dated rows for current filters (or posted_date is null).")

    with tab3:
        st.caption("Tip: open a row’s job URL in a new tab; descriptions are truncated in the grid.")
        list_sql = f"""
        SELECT
          job_title,
          company_name,
          location,
          posted_date,
          source_id,
          job_url,
          SUBSTR(COALESCE(job_description, ''), 1, 400) AS description_preview
        FROM {jobs_fqn}
        WHERE {where_sql}
        ORDER BY posted_date DESC NULLS LAST, job_title ASC NULLS LAST
        LIMIT @lim
        """
        lp = list(params) + [bigquery.ScalarQueryParameter("lim", "INT64", int(limit))]
        job_rows = run_query(client, list_sql, lp)
        if not job_rows:
            st.info("No rows for current filters.")
        else:
            df_jobs = pd.DataFrame(job_rows)
            st.dataframe(df_jobs, use_container_width=True, hide_index=True)
            csv = df_jobs.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download CSV (current page)",
                data=csv,
                file_name="horizon_jobs_export.csv",
                mime="text/csv",
            )

    with st.expander("About this app"):
        st.markdown(
            """
- **Data**: `master_jobs` (union of `raw_*` tables) if you ran `scripts/create_master_table.py`;
  otherwise one selected **`raw_*`** table.
- **Refresh data**: run `run_ingestion.py` → `scripts/load_gcs_to_bigquery.py` → optional `create_master_table.py`.
- **Credentials**: same ADC as other Horizon scripts; no API keys in the UI.
            """
        )


if __name__ == "__main__":
    main()
