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

from ingestion.env_bootstrap import load_dotenv_repo  # noqa: E402

load_dotenv_repo()

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from google.cloud import bigquery  # noqa: E402

from streamlit_app.bq_helpers import (  # noqa: E402
    bq_client,
    get_dataset_id,
    get_project_id,
    list_raw_tables,
    qualifying_raw_table,
    resolve_jobs_relation,
    run_query,
    skills_normalized_array_sql,
    sort_source_ids_huggingface_first,
    table_has_column,
)

st.set_page_config(
    page_title="Horizon — Job Explorer",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

_RAW_TABLE_LABELS = {
    "raw_huggingface_data_jobs": "Hugging Face — data jobs",
    "raw_kaggle_data_engineer_2023": "Kaggle — Data Engineer 2023",
    "raw_kaggle_linkedin_postings": "Kaggle — LinkedIn postings",
    "raw_kaggle_linkedin_jobs_skills_2024": "Kaggle — LinkedIn jobs & skills 2024",
}


def _raw_table_display_name(table_id: str) -> str:
    return _RAW_TABLE_LABELS.get(table_id, table_id.replace("raw_", "").replace("_", " ").title())


@st.cache_resource
def _client(project: str) -> bigquery.Client:
    return bq_client(project)


def main() -> None:
    project = get_project_id()
    dataset = get_dataset_id()

    if not project:
        st.error(
            "This app needs your GCP project ID. Add **GOOGLE_CLOUD_PROJECT** (or **GCP_PROJECT**) "
            "to a `.env` file in the repo root, or set it before running Streamlit. "
            "BigQuery access uses **Application Default Credentials** "
            "(run `gcloud auth application-default login`)."
        )
        st.stop()

    client = _client(project)

    try:
        fqn, mode = resolve_jobs_relation(client, project, dataset)
    except RuntimeError as e:
        st.error(str(e))
        st.stop()

    raw_list = list_raw_tables(client, project, dataset)
    jobs_fqn = fqn
    source_options: list[str] | None = None
    if mode == "master_jobs" and raw_list:
        counts_sql = f"""
        SELECT source_id, COUNT(*) AS n
        FROM {jobs_fqn}
        GROUP BY 1
        ORDER BY n DESC
        """
        src_rows = run_query(client, counts_sql)
        source_options = sort_source_ids_huggingface_first(
            [r["source_id"] for r in src_rows if r.get("source_id")]
        )

    with st.sidebar:
        if mode == "raw_pick":
            st.markdown("### Dataset")
            raw_sorted = sorted(
                raw_list,
                key=lambda t: (0 if "huggingface" in t.lower() else 1, t),
            )
            labels = [_raw_table_display_name(t) for t in raw_sorted]
            label_to_id = dict(zip(labels, raw_sorted))
            choice_lbl = st.selectbox(
                "Which table to explore",
                options=labels,
                index=0,
                help="Pick one loaded table, or run create_master_table.py to combine everything.",
            )
            jobs_fqn = qualifying_raw_table(project, dataset, label_to_id[choice_lbl])

        st.markdown("### Filters")
        st.caption("Narrow the numbers and tables below. Defaults include all sources.")

        if source_options:
            sources_filter = st.multiselect(
                "Show data from",
                options=source_options,
                default=source_options,
                help="Job postings come from several providers; Hugging Face is listed first.",
            )
        else:
            sources_filter = []

        use_dates = st.checkbox("Limit by posted date", value=False)
        d_start = d_end = None
        if use_dates:
            col_a, col_b = st.columns(2)
            with col_a:
                d_start = st.date_input("From", value=None, key="d0")
            with col_b:
                d_end = st.date_input("To", value=None, key="d1")

        search = st.text_input(
            "Search in title or description",
            placeholder="Examples: analyst, Python, remote",
            value="",
        )
        limit = st.slider(
            "How many rows in Browse tab",
            min_value=50,
            max_value=2000,
            value=200,
            step=50,
        )

    # ---------- Main: intro + metrics ----------
    st.title("Job posting explorer")
    st.markdown(
        """
**What this does:** browse unified tech job postings collected from **Hugging Face** and **Kaggle**
in one place. Use **Filters** on the left, then open the tabs for **sources**, **trends**, **skills by year**,
**top employers**, and **browse** with CSV export.
        """.strip()
    )

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

    if source_options is not None:
        sources_metric_val = str(len(source_options))
    elif mode in ("raw_single", "raw_pick"):
        sources_metric_val = "1"
    else:
        sources_metric_val = "—"

    complete_n: int | None = None
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
                complete_n = int(run_query(client, comp_sql, params)[0]["complete_rows"] or 0)
        except Exception:
            complete_n = None

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Postings (with filters)", f"{int(total):,}")
    m2.metric("Sources in view", sources_metric_val)
    m3.metric(
        "Dataset",
        "All combined" if mode == "master_jobs" else "One table",
        help="Combined view lists Hugging Face first when you compare sources.",
    )
    if complete_n is not None:
        m4.metric("Quality: complete rows", f"{complete_n:,}", help="Rows with title and description or skills.")
    else:
        m4.metric("Tip", "5 tabs →", help="Sources, trends, skills, companies, browse.")

    tab_sources, tab_time, tab_skills, tab_companies, tab_browse = st.tabs(
        [
            "1 — Compare sources",
            "2 — Volume over time",
            "3 — Top skills by year",
            "4 — Top hiring companies",
            "5 — Browse & export",
        ]
    )

    with tab_sources:
        st.markdown("**Postings per data source.** Hugging Face is shown first in the list and chart when present.")
        sql_src = f"""
        SELECT source_id, COUNT(*) AS job_count
        FROM {jobs_fqn}
        WHERE {where_sql}
        GROUP BY 1
        ORDER BY job_count DESC
        """
        rows = run_query(client, sql_src, params)
        if rows:
            order = sort_source_ids_huggingface_first([r["source_id"] for r in rows if r.get("source_id")])
            rank = {sid: i for i, sid in enumerate(order)}
            rows_sorted = sorted(rows, key=lambda r: rank.get(r["source_id"], 999))
            df = pd.DataFrame(rows_sorted)
            st.bar_chart(df.set_index("source_id")[["job_count"]])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No rows match your filters. Loosen filters in the sidebar.")

    with tab_time:
        st.markdown("**Monthly posting counts** (all selected sources together). Dates must exist on the row.")
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
            st.line_chart(tdf.set_index("month")[["job_count"]])
            st.dataframe(tdf, use_container_width=True, hide_index=True)
        else:
            st.info("No dated rows for these filters, or `posted_date` is empty.")

    with tab_skills:
        st.markdown(
            "**Top 10 skills per calendar year** (from parsed `skills` on each job row). "
            "Rows need a **non-null `posted_date`** and at least one skill; respects the same filters as other tabs."
        )
        if not table_has_column(client, jobs_fqn, "skills"):
            st.warning("This dataset has no **`skills`** column — skip this tab or use a union that includes skills.")
        else:
            unnest_sql = skills_normalized_array_sql("skills")
            sql_skills = f"""
            WITH filtered_jobs AS (
              SELECT posted_date, skills
              FROM {jobs_fqn}
              WHERE {where_sql}
                AND posted_date IS NOT NULL
            ),
            skill_rows AS (
              SELECT
                EXTRACT(YEAR FROM posted_date) AS job_year,
                TRIM(skill) AS skill
              FROM filtered_jobs,
              UNNEST({unnest_sql}) AS skill
              WHERE TRIM(skill) IS NOT NULL AND skill != ''
            ),
            year_skill_counts AS (
              SELECT job_year, skill, COUNT(*) AS skill_count
              FROM skill_rows
              GROUP BY 1, 2
            ),
            ranked AS (
              SELECT
                job_year,
                skill,
                skill_count,
                ROW_NUMBER() OVER (PARTITION BY job_year ORDER BY skill_count DESC, skill ASC) AS rank_in_year
              FROM year_skill_counts
            )
            SELECT job_year, skill, skill_count, rank_in_year
            FROM ranked
            WHERE rank_in_year <= 10
            ORDER BY job_year DESC, rank_in_year ASC
            """
            try:
                skill_rows = run_query(client, sql_skills, params)
            except Exception as e:
                st.error(f"Could not run skills query: {e}")
                skill_rows = []
            if not skill_rows:
                st.info(
                    "No skill mentions for these filters. Ensure ingestion populated **`skills`** "
                    "(e.g. taxonomy extraction for some Kaggle sources; see docs/MASTER_TABLE_SPEC.md)."
                )
            else:
                sdf = pd.DataFrame(skill_rows)
                years = sorted({int(y) for y in sdf["job_year"].dropna().tolist()}, reverse=True)
                pick = st.selectbox("Year to chart", options=years, index=0, key="skills_year_pick")
                sub = sdf[sdf["job_year"] == int(pick)].sort_values("rank_in_year")
                chart_df = sub.set_index("skill")[["skill_count"]].sort_values("skill_count")
                st.bar_chart(chart_df)
                st.caption("Full top-10 list per year (table below).")
                st.dataframe(
                    sdf.sort_values(["job_year", "rank_in_year"], ascending=[False, True]),
                    use_container_width=True,
                    hide_index=True,
                )

    with tab_companies:
        st.markdown(
            "**Top 10 organizations by posting count** in the filtered set (non-empty **`company_name`**). "
            "Useful for seeing who is hiring most often in the current slice of data."
        )
        if not table_has_column(client, jobs_fqn, "company_name"):
            st.warning("No **`company_name`** column on this relation.")
        else:
            sql_co = f"""
            SELECT TRIM(company_name) AS company_name, COUNT(*) AS job_count
            FROM {jobs_fqn}
            WHERE {where_sql}
              AND company_name IS NOT NULL
              AND TRIM(company_name) != ''
            GROUP BY 1
            ORDER BY job_count DESC
            LIMIT 10
            """
            try:
                co_rows = run_query(client, sql_co, params)
            except Exception as e:
                st.error(f"Could not run company ranking query: {e}")
                co_rows = []
            if not co_rows:
                st.info("No companies match these filters, or `company_name` is mostly empty.")
            else:
                cdf = pd.DataFrame(co_rows)
                st.bar_chart(
                    cdf.set_index("company_name")[["job_count"]].sort_values("job_count")
                )
                st.dataframe(cdf, use_container_width=True, hide_index=True)

    with tab_browse:
        st.markdown(
            "**Job list** — Hugging Face postings appear **first**, then others by date. "
            "Open **job_url** in a new tab for the full posting."
        )
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
        ORDER BY
          CASE WHEN LOWER(COALESCE(source_id, '')) LIKE '%huggingface%' THEN 0 ELSE 1 END,
          posted_date DESC NULLS LAST,
          job_title ASC NULLS LAST
        LIMIT @lim
        """
        lp = list(params) + [bigquery.ScalarQueryParameter("lim", "INT64", int(limit))]
        job_rows = run_query(client, list_sql, lp)
        if not job_rows:
            st.info("No rows match your filters.")
        else:
            df_jobs = pd.DataFrame(job_rows)
            st.dataframe(df_jobs, use_container_width=True, hide_index=True)
            csv = df_jobs.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download this table as CSV",
                data=csv,
                file_name="horizon_jobs_export.csv",
                mime="text/csv",
            )

    with st.expander("For developers / refresh pipeline"):
        st.markdown(
            """
- **Data location:** BigQuery — a combined **`master_jobs`** view is recommended; otherwise a single **`raw_*`** table.
- **Reload pipeline:** ingest → **`scripts/load_gcs_to_bigquery.py`** → optional **`scripts/create_master_table.py`**.
- **Credentials:** The server or your laptop supplies GCP access (e.g. Cloud Run SA or
  `gcloud auth application-default login`). This UI does **not** show project IDs or account names.
            """.strip()
        )


if __name__ == "__main__":
    main()
