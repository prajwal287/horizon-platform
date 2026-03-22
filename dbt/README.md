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
| `mart_jobs_curated` | Primary job-level table (`is_complete`, quality bucket, deduped) |
| `mart_posting_volume` | Monthly volume by source |
| `mart_skill_demand` | Skill counts |
| `mart_cross_source_urls` | Same URL across multiple sources |

## Docs

See **[docs/DBT_INTEGRATION.md](../docs/DBT_INTEGRATION.md)** for the full diagram, logic, and how to extend macros/models.

**Note:** Remove unused tables from `models/sources.yml` if you do not load all five raw sources.
