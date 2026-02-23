# Horizon

The Data Architecture & Agentic AI Intelligence Platform — data-domain job postings ingestion (Hugging Face + Kaggle) via **dlt → GCS (Parquet) → BigQuery**. Work primarily in BigQuery with optional Spark jobs.

## Architecture: dlt → GCS → BigQuery

1. **Step 1 — dlt → GCS (Parquet)**  
   `run_ingestion.py` loads sources (Hugging Face, Kaggle) and writes Parquet to GCS under `gs://<bucket>/raw/<source_slug>/` (e.g. `raw/huggingface_data_jobs/`, `raw/kaggle_data_engineer_2023/`).

2. **Step 2 — GCS → BigQuery**  
   `scripts/load_gcs_to_bigquery.py` loads those Parquet files into BigQuery tables in dataset `job_market_analysis` (e.g. `raw_huggingface_data_jobs`, `raw_kaggle_data_engineer_2023`).

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

6. **Step 1 — Ingest to GCS (Parquet)**:
   ```bash
   docker compose run --rm app python run_ingestion.py --source all
   ```
   Or run a single source: `--source huggingface`, `--source kaggle_data_engineer`, etc.

7. **Step 2 — Load GCS Parquet into BigQuery**:
   ```bash
   docker compose run --rm app python scripts/load_gcs_to_bigquery.py --source all
   ```
   Or load a single source: `--source kaggle_data_engineer`, etc.

After both steps, tables `raw_huggingface_data_jobs`, `raw_kaggle_data_engineer_2023`, etc. appear in BigQuery dataset `job_market_analysis`.

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
- **ingestion/** — dlt pipelines (step 1: write Parquet to GCS).
- **scripts/** — `inspect_kaggle_csv.py`, `load_gcs_to_bigquery.py` (step 2: GCS → BigQuery).
- **run_ingestion.py** — CLI for step 1 (dlt → GCS).

See [terraform/README.md](terraform/README.md) for infrastructure setup.
