# When to Use dbt for Transformation Steps

This doc helps you decide **when** to introduce **dbt** (data build tool) for transformations on top of your current pipeline (dlt → GCS → BigQuery raw tables → master table).

---

## What you have today

| Layer        | How it's built                          | Where it lives        |
|-------------|------------------------------------------|------------------------|
| **Ingestion** | `run_ingestion.py` (dlt) → Parquet       | GCS                    |
| **Raw**       | `load_gcs_to_bigquery.py` → raw_* tables | BigQuery               |
| **Master**    | `create_master_table.py` → view/table    | BigQuery `master_jobs` |

Transformations are currently:

- **Light**: union of raw tables, consistent types, one quality flag (`is_complete`) in the clean view.
- **Implemented in**: SQL files under `scripts/sql/` and Python in `scripts/create_master_table.py`.

---

## When to **keep the current approach** (no dbt)

Stay with Python + SQL scripts when:

- You have **few transformation steps** (e.g. one union, one clean view, one filter).
- **One or few people** run the pipeline; no need for a shared, versioned DAG.
- You want **minimal tooling**: run a script after load and you’re done.
- You don’t need **incremental** or **in-database only** refreshes; full refresh is fine.

**Recommendation:** For the current “raw → master (with optional clean)” flow, the existing scripts are enough. Use `create_master_table.py` (with `--clean` and/or `--materialize` as needed) and only consider dbt when you cross the thresholds below.

---

## When to **introduce dbt** for transformations

Introduce dbt when you need one or more of the following.

### 1. **Multiple transformation layers (Bronze → Silver → Gold)**

- **Bronze**: raw tables (what you have now).
- **Silver**: cleaned, typed, deduplicated, one row per business key (e.g. `stg_*` or `silver_*`).
- **Gold**: aggregated / analytics tables (e.g. skills summary, job counts by source, by month).

If you start adding several Silver models (e.g. `stg_jobs`, `stg_skills_flattened`) and Gold models (e.g. `gold_skills_frequency`, `gold_jobs_by_month`), dbt keeps dependencies and order clear and testable.

### 2. **Reusable, testable, documented SQL**

- You want **tests** (e.g. uniqueness on `(source_id, job_id)`, not-null on key columns).
- You want **documentation** (column descriptions, lineage) generated from the project.
- You want **ref()** and **source()** so models stay in sync when table names change.

### 3. **Incremental or more complex refresh logic**

- You want **incremental** models (e.g. only new/changed rows) instead of full truncate/insert.
- You have **multiple steps** that should run in a defined order with a single command (`dbt run`).

### 4. **Team and CI/CD**

- **Several people** contribute transformations; you want a single place (dbt project) and standard commands.
- You want **CI** to run `dbt build` (or `dbt run` + `dbt test`) on every change.

### 5. **Governance and lineage**

- You want **lineage graphs** (raw → staging → gold) and exposure to BI tools.
- You’re standardizing on **dbt + BigQuery** (or dbt Cloud) for all analytics transformations.

---

## How to adopt dbt later (high level)

When you decide to move transformations into dbt:

1. **Keep ingestion and load as-is**  
   dlt → GCS and `load_gcs_to_bigquery.py` stay the same; dbt only reads from BigQuery.

2. **Point dbt at your dataset**  
   In `profiles.yml`, set the BigQuery project and dataset (e.g. `job_market_analysis`) where raw and master tables live.

3. **Add sources**
   Define `raw_huggingface_data_jobs`, `raw_kaggle_data_engineer_2023`, `raw_jobven_jobs`, etc. as dbt **sources**.

4. **Move union + clean into dbt models**  
   - e.g. `stg_master_jobs.sql`: union of raw tables with consistent types (and `is_complete` if you like).  
   - Optionally a **mart** like `mart_master_jobs_clean` that filters `WHERE is_complete = TRUE`.

5. **Add more models as needed**  
   Staging per source, gold aggregates, etc. Use **ref()** between models so lineage and order are automatic.

6. **Run after load**  
   After `load_gcs_to_bigquery.py`, run `dbt run` (and `dbt test`) so transformations stay up to date.

---

## Summary

| Situation                                      | Use now                         | Consider dbt when                                      |
|-----------------------------------------------|----------------------------------|--------------------------------------------------------|
| Single master union (raw → one table/view)    | `create_master_table.py`        | You add Silver/Gold layers and multiple models         |
| Need consistent types + quality flag          | `create_master_table.py --clean`| You want tests, docs, lineage, incremental             |
| One-off or small team, full refresh OK        | Current scripts                 | Team grows or you need incremental / complex logic     |
| Many models, tests, docs, CI, lineage         | —                               | **Introduce dbt** and move transformation SQL into dbt |

**Bottom line:** Use the current master table script until your transformation layer grows (more models, tests, incremental logic, or team collaboration). Then add dbt for those transformation steps and keep ingestion (dlt + load to BQ) unchanged.
