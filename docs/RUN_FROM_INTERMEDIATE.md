# Run From Where You Left Off (Intermediate Steps)

Use this when **GCP and data already exist** from a previous run. You do **not** re-run Terraform or full ingestion from scratch.

---

## When to use this

- You already ran **Step 1** (ingestion → Parquet in GCS) and **Step 2** (load → BigQuery) at least once.
- You want to: refresh one source, add skills, rebuild the master table, or run only later steps.

---

## 1. Check your current state

From project root, with `.env` or env vars set:

```bash
# GCS: list Parquet (replace BUCKET with your GCS_BUCKET)
gsutil ls gs://BUCKET/raw/

# BigQuery: list raw tables (replace PROJECT and DATASET)
bq ls --project_id=PROJECT DATASET
```

You should see folders like `raw/huggingface_data_jobs/`, `raw/kaggle_data_engineer_2023/` in GCS and tables like `raw_kaggle_data_engineer_2023` in BigQuery.

---

## 2. Resume options (pick what you need)

### A. Refresh one source only (e.g. Kaggle Data Engineer)

Re-ingest that source and reload it into BigQuery. Other sources are untouched.

```bash
# Optional: add skills from job description
export EXTRACT_SKILLS_TAXONOMY=1

python3 run_ingestion.py --source kaggle_data_engineer
python3 scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer
```

### B. Refresh all sources (full re-run of Steps 1 and 2)

Same as a full run, but you don’t need to run Terraform or create the bucket/dataset again.

```bash
export GCS_BUCKET=your-bucket
export GOOGLE_CLOUD_PROJECT=your-project
export BIGQUERY_DATASET=job_market_analysis
# Kaggle (if using Kaggle sources):
export KAGGLE_USERNAME=your_username
export KAGGLE_KEY=your_key

python3 run_ingestion.py --source all
python3 scripts/load_gcs_to_bigquery.py --source all
```

### C. Only rebuild the master table (no ingestion, no load)

Use this when raw tables already exist and you only want to update the `master_jobs` view or table.

```bash
export GOOGLE_CLOUD_PROJECT=your-project
export BIGQUERY_DATASET=job_market_analysis

# View (union of existing raw tables)
python3 scripts/create_master_table.py --clean

# Or materialized table (faster for heavy queries)
python3 scripts/create_master_table.py --clean --create-table   # once
python3 scripts/create_master_table.py --clean --materialize    # each refresh
```

### D. Only run Step 2 (GCS → BigQuery)

Use when Parquet in GCS is already up to date and you only want to reload BigQuery.

```bash
python3 scripts/load_gcs_to_bigquery.py --source all
# Then optionally:
python3 scripts/create_master_table.py --clean
```

---

## 3. Env vars you need (no Terraform)

| Step | Required env |
|------|----------------|
| Step 1 (ingestion) | `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT` (or `GCP_PROJECT`). For Kaggle: `KAGGLE_USERNAME`, `KAGGLE_KEY`. |
| Step 2 (load to BQ) | `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT`, `BIGQUERY_DATASET` (default `job_market_analysis`). |
| Master table | `GOOGLE_CLOUD_PROJECT`, `BIGQUERY_DATASET`. |

GCP auth: `gcloud auth application-default login` (once per machine).

---

## 4. Quick reference

| Goal | Commands |
|------|----------|
| Refresh one source + skills | `EXTRACT_SKILLS_TAXONOMY=1 python3 run_ingestion.py --source SOURCE` then `python3 scripts/load_gcs_to_bigquery.py --source SOURCE` |
| Refresh all data | `python3 run_ingestion.py --source all` then `python3 scripts/load_gcs_to_bigquery.py --source all` |
| Only update BigQuery from existing GCS | `python3 scripts/load_gcs_to_bigquery.py --source all` |
| Only update master_jobs | `python3 scripts/create_master_table.py --clean` |

For first-time setup (Terraform, empty GCS/BQ), use **RUN_FROM_SCRATCH.md** and **RUN_SCRIPTS.md** instead.
