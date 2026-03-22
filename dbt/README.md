# dbt (BigQuery) — transformations only

Ingestion stays in the parent repo (`run_ingestion.py`, `load_gcs_to_bigquery.py`). This folder defines **SQL models** on top of existing **`raw_*`** tables.

## Quick start

```bash
pip install dbt-bigquery
cp profiles.yml.example ~/.dbt/profiles.yml
# Edit ~/.dbt/profiles.yml: project, dataset, location

export GOOGLE_CLOUD_PROJECT=your-project-id
export BIGQUERY_DATASET=job_market_analysis
cd dbt
dbt debug
dbt run
```

See **[docs/DBT_INTEGRATION.md](../docs/DBT_INTEGRATION.md)** for architecture, run order after loads, and how to extend models.

## Layout

- `models/sources.yml` — BigQuery sources = `raw_*` tables
- `models/marts/master_jobs_clean.sql` — union + `is_complete` → view in **`dbt_marts`**

Remove or comment sources in `sources.yml` for tables you do not load (e.g. Jobven).
