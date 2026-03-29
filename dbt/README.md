# dbt — Bronze / Silver / Gold on BigQuery

Ingestion stays in the parent repo. This project transforms **`raw_*`** into **`dbt_bronze`** → **`dbt_silver`** → **`dbt_gold`**.

## Quick start

```bash
pip install -r ../requirements-dev.txt   # or: pip install "dbt-bigquery>=1.10,<1.11"
cp profiles.yml.example ~/.dbt/profiles.yml

export GOOGLE_CLOUD_PROJECT=horizon-platform-488122   # your real GCP project id (never YOUR_GCP_PROJECT_ID)
export BIGQUERY_DATASET=job_market_analysis           # optional; default is already this in profiles example
cd dbt
dbt debug
dbt run
dbt test
```

The profile uses **`env_var('GOOGLE_CLOUD_PROJECT')`**. If dbt errors with `projects/YOUR_GCP_PROJECT_ID`, your shell or an old `~/.dbt/profiles.yml` still has the placeholder—fix the env var or re-copy **`profiles.yml.example`**.

## Main gold outputs

| Model | Use |
|-------|-----|
| `mart_jobs_curated` | Primary job-level **table**: partitioned by `posted_date` (month), clustered by `source_id`, `content_quality_bucket` |
| `mart_posting_volume` | Monthly volume by source — **table**: partitioned by `posting_month`, clustered by `source_id` |
| `mart_skill_demand` | Skill counts |
| `mart_cross_source_urls` | Same URL across multiple sources |

## Docs

See **[docs/GUIDE_DLT_DBT.md](../docs/GUIDE_DLT_DBT.md)** for how ingestion and dbt connect, scenario walkthroughs, and how to extend models.

**Note:** Remove unused tables from `models/sources.yml` if you do not load all five raw sources.
