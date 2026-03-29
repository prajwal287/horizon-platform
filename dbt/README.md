# dbt — Bronze / Silver / Gold on BigQuery

Ingestion stays in the parent repo. This project transforms **`raw_*`** into **`dbt_bronze`** → **`dbt_silver`** → **`dbt_gold`**.

## Quick start

```bash
pip install dbt-bigquery
cp profiles.yml.example ~/.dbt/profiles.yml   # set project, location

export GOOGLE_CLOUD_PROJECT=your-project-id
export BIGQUERY_DATASET=job_market_analysis
cd dbt
dbt debug
dbt run
dbt test
```

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
