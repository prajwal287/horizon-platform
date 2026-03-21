# Horizon

The Data Architecture & Agentic AI Intelligence Platform — data-domain job postings ingestion (Hugging Face, Kaggle, Jobven) via **dlt → GCS (Parquet) → BigQuery**. Work primarily in BigQuery with optional Spark jobs.

## Architecture: dlt → GCS → BigQuery

1. **Step 1 — dlt → GCS (Parquet)**  
   `run_ingestion.py` loads sources (Hugging Face, Kaggle, Jobven) and writes Parquet to GCS under `gs://<bucket>/raw/<source_slug>/` (e.g. `raw/huggingface_data_jobs/`, `raw/kaggle_data_engineer_2023/`, `raw/jobven_jobs/`).

2. **Step 2 — GCS → BigQuery**  
   `scripts/load_gcs_to_bigquery.py` loads those Parquet files into BigQuery tables in dataset `job_market_analysis` (e.g. `raw_huggingface_data_jobs`, `raw_kaggle_data_engineer_2023`, `raw_jobven_jobs`).

3. **Analytics**  
   Run SQL and dbt in BigQuery; Silver/Gold tables live in the same dataset. Spark can read/write BigQuery or GCS as needed.

## Running the pipeline (two steps)

1. **Rebuild the image** (from project root):
   ```bash
   docker compose build
   ```

2. **GCP credentials and project** (required for GCS and BigQuery):
   - **Application Default Credentials**: `gcloud auth application-default login`
   - **Project ID**: `export GOOGLE_CLOUD_PROJECT=$(terraform -chdir=terraform output -raw project_id)` (or set in `.env`)

3. **GCS bucket** (required for step 1):
   ```bash
   export GCS_BUCKET=$(terraform -chdir=terraform output -raw gcs_bucket_name)
   ```
   Or set `GCS_BUCKET=...` in `.env`.

4. **BigQuery dataset** (optional for step 2; default `job_market_analysis`):
   ```bash
   export BIGQUERY_DATASET=$(terraform -chdir=terraform output -raw bigquery_dataset_id)
   ```

5. **Kaggle credentials** (required for Kaggle sources only): set `KAGGLE_USERNAME` and `KAGGLE_API_TOKEN` (or `KAGGLE_KEY`) in `.env`.

6. **Jobven** (optional, free tier): set `JOBVEN_API_KEY` in `.env` to include US jobs from the last 24h. See [RUN_SCRIPTS.md](docs/RUN_SCRIPTS.md) for limits.

7. **Step 1 — Ingest to GCS (Parquet)**:
   ```bash
   docker compose run --rm app python run_ingestion.py --source all
   ```
   Or run a single source: `--source huggingface`, `--source kaggle_data_engineer`, `--source jobven`, etc.

8. **Step 2 — Load GCS Parquet into BigQuery**:
   ```bash
   docker compose run --rm app python scripts/load_gcs_to_bigquery.py --source all
   ```
   Or load a single source: `--source kaggle_data_engineer`, `--source jobven`, etc.

After both steps, tables `raw_huggingface_data_jobs`, `raw_kaggle_data_engineer_2023`, `raw_jobven_jobs`, etc. appear in BigQuery dataset `job_market_analysis`.

## Inspecting Kaggle CSV columns (for correct mapping)

```bash
docker compose run --rm app python scripts/inspect_kaggle_csv.py kaggle_data_engineer
```

For other Kaggle sources: `kaggle_linkedin`, `kaggle_linkedin_skills`.

## Spark jobs (optional)

- **BigQuery**: Use the BigQuery connector for Spark to read/write `job_market_analysis.raw_*` (e.g. from Dataproc).
- **GCS**: Parquet in `gs://<bucket>/raw/<source_slug>/` is available for Spark reads/writes.

## Project layout

- **terraform/** — GCP IaC (GCS, BigQuery, Pub/Sub, service account).
- **ingestion/** — dlt pipelines (step 1: write Parquet to GCS). Shared runner and schema in `ingestion/pipelines/common.py` and `ingestion/schema.py`.
- **scripts/** — `load_gcs_to_bigquery.py` (step 2: GCS → BigQuery), `create_master_table.py` (master_jobs view/table), `compare_skills_extraction.py` (eval), `inspect_kaggle_csv.py` (dev helper).
- **run_ingestion.py** — CLI for step 1 (dlt → GCS).

## Documentation

- **[EXECUTION_CHECKLIST.md](docs/EXECUTION_CHECKLIST.md)** — Phase-by-phase runbook with exact commands and done criteria.
- **[DLT_LEARNING.md](docs/DLT_LEARNING.md)** — Learn dlt using this repo: concepts, HF vs Kaggle, `replace` + Parquet, exercises.
- **[RUN_SCRIPTS.md](docs/RUN_SCRIPTS.md)** — How to run: ingestion, load to BigQuery, master table, skills.
- **[HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)** — How the code works end-to-end (flow, which file does what).
- **[RUN_FROM_SCRATCH.md](docs/RUN_FROM_SCRATCH.md)** — First-time setup: Terraform, GCP, then run pipeline.
- **[RUN_FROM_INTERMEDIATE.md](docs/RUN_FROM_INTERMEDIATE.md)** — Resume from where you left off (no full re-run).
- [MASTER_TABLE_SPEC.md](docs/MASTER_TABLE_SPEC.md) — Master table columns, adding skills, clean view.
- [WHEN_TO_USE_DBT.md](docs/WHEN_TO_USE_DBT.md) — When to introduce dbt for transformations.
- [EVALUATE_SKILLS_EXTRACTION.md](docs/EVALUATE_SKILLS_EXTRACTION.md) — Compare taxonomy vs LLM skills.
- [terraform/README.md](terraform/README.md) — Infrastructure setup.
