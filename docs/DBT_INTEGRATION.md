# Incorporating dbt into this codebase

This doc explains **where dbt fits** next to **dlt → GCS → BigQuery** and how to use the **`dbt/`** starter in this repo.

**Related:** [WHEN_TO_USE_DBT.md](WHEN_TO_USE_DBT.md) (when transformation logic deserves dbt vs keeping Python/SQL scripts).

---

## Architecture (unchanged ingestion)

```
run_ingestion.py (dlt)  →  GCS Parquet
load_gcs_to_bigquery.py →  BigQuery raw_*   ← dbt sources (read-only)
dbt run / dbt build     →  BigQuery dbt_marts.*  (or your chosen dataset)
```

- **Do not** replace dlt ingestion with dbt; dbt does not pull from APIs/CSV the way this repo does.
- **Do** use dbt for **transformations inside BigQuery**: staging, unions, cleans, aggregates, tests, docs.

You can **keep** `scripts/create_master_table.py` while evaluating dbt, or **stop running it** once `dbt_marts.master_jobs_clean` (or equivalent) is your source of truth.

---

## Prerequisites

1. **Python 3.10+** recommended (dbt aligns with current `google-*` stacks; your app may still use 3.9 for ingestion).
2. **BigQuery access** with the same identity you use for loads: `gcloud auth application-default login`.
3. **Raw tables loaded** at least once (`load_gcs_to_bigquery.py`), in dataset `job_market_analysis` (or whatever you set in Terraform / `.env`).

Install dbt with the BigQuery adapter (in a venv or globally):

```bash
pip install dbt-bigquery
```

---

## One-time setup

### 1. Configure `profiles.yml`

dbt reads **`~/.dbt/profiles.yml`** (not committed). Copy the example:

```bash
cp dbt/profiles.yml.example ~/.dbt/profiles.yml
```

Edit **`project`**, **`dataset`** (raw dataset name), and **`location`** to match your GCP project. For **`method: oauth`**, dbt uses **Application Default Credentials** (same as `gcloud auth application-default login`).

### 2. Environment variables for sources

The starter **`sources.yml`** uses:

- **`GOOGLE_CLOUD_PROJECT`** — GCP project ID (same as ingestion).
- **`BIGQUERY_DATASET`** — dataset where `raw_*` tables live (default `job_market_analysis`).

```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
export BIGQUERY_DATASET=job_market_analysis
cd dbt
dbt debug
```

`dbt debug` should report “All checks passed”.

### 3. Run models

From the **`dbt/`** directory:

```bash
dbt run
```

Models materialize into the **`dbt_marts`** BigQuery dataset (see `dbt/dbt_project.yml`) so they do not overwrite `raw_*` tables.

---

## After each data refresh

Typical order:

```bash
# 1–2: existing pipeline (from repo root)
python3 run_ingestion.py --source all
python3 scripts/load_gcs_to_bigquery.py --source all

# 3: transformations
cd dbt && dbt run && dbt test
```

Add **`dbt test`** once you define tests in YAML. Optionally **`dbt docs generate && dbt docs serve`** for lineage and column docs.

---

## What the starter project contains

| Path | Purpose |
|------|---------|
| `dbt/dbt_project.yml` | Project name, model defaults, `dbt_marts` schema for marts |
| `dbt/models/sources.yml` | Declares **`lakehouse_raw`** sources = your `raw_*` tables |
| `dbt/models/marts/master_jobs_clean.sql` | Union + `is_complete` (parity with `scripts/sql/master_jobs_clean_view.sql`) |

**Caveat:** `dbt run` expects every **sourced** table to exist. If you never load Jobven, either remove `raw_jobven_jobs` from `sources.yml` or add a placeholder empty table—otherwise BigQuery will error on missing tables.

---

## Next steps (grow the project)

1. **Staging per source:** `stg_huggingface.sql` etc. with `select * from {{ source(...) }}` plus light renames/casts.
2. **Gold / marts:** e.g. `mart_jobs_by_source_month.sql`, skills unnest models.
3. **Tests:** `unique`, `not_null`, relationships in `schema.yml`.
4. **CI:** run `dbt build` on pull requests with a service account JSON secret (not ADC).
5. **Incremental models:** for append-only snapshots if you change ingestion to append instead of truncate (separate design).

---

## Summary

| Layer | Tool | Location |
|-------|------|----------|
| Ingest | dlt + Python | `run_ingestion.py`, `ingestion/` |
| Raw in BQ | Python + BQ load | `scripts/load_gcs_to_bigquery.py` |
| Transform | **dbt** | **`dbt/`** (starter) + your new models |

**Bottom line:** keep ingestion/load as-is; add dbt for BigQuery-only transforms, run **`dbt run`** after each load, and point BI tools at **`project.dbt_marts.master_jobs_clean`** (or models you add).
