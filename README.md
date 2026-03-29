# Horizon

Job-posting data pipeline and dashboard — ingest Hugging Face and Kaggle sources via **dlt → GCS (Parquet) → BigQuery**, with **dbt** medallion marts and a **Streamlit** explorer (categorical + time-series charts). Work primarily in BigQuery; Spark is optional.

**Problem it solves:** postings live in separate public datasets; this repo **unifies** them in a **GCP lake + warehouse**, adds **curated marts** (partitioned/clustered where it matters), and gives analysts a **small dashboard** without ad-hoc notebooks. **Peer-review / rubric mapping:** [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md).

## Architecture: dlt → GCS → BigQuery

1. **Step 1 — dlt → GCS (Parquet)**  
   `run_ingestion.py` loads sources (Hugging Face, Kaggle) and writes Parquet to GCS under `gs://<bucket>/raw/<source_slug>/` (e.g. `raw/huggingface_data_jobs/`, `raw/kaggle_data_engineer_2023/`).

2. **Step 2 — GCS → BigQuery**  
   `scripts/load_gcs_to_bigquery.py` loads those Parquet files into BigQuery tables in dataset `job_market_analysis` (e.g. `raw_huggingface_data_jobs`, `raw_kaggle_data_engineer_2023`).

3. **Analytics**  
   Run SQL in BigQuery on `raw_*` / `master_jobs`; **dbt** builds bronze, silver, and gold in datasets with suffixes like `_dbt_bronze`, `_dbt_silver`, `_dbt_gold`. Spark can read/write BigQuery or GCS as needed.

## Running the pipeline

**One-shot batch sequence** (ingest → load → `master_jobs` → dbt): `./scripts/run_batch_pipeline.sh` (see [docs/GUIDE_END_TO_END.md](docs/GUIDE_END_TO_END.md); set `SKIP_DBT=1` if you have not installed `dbt-bigquery` yet).

**Manual two-step core** (lake + raw tables only):

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

After both steps, tables such as `raw_huggingface_data_jobs` and `raw_kaggle_data_engineer_2023` appear in BigQuery dataset `job_market_analysis`.

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
- **scripts/** — `run_batch_pipeline.sh` (orchestrated batch: lake → BQ → master → dbt), `load_gcs_to_bigquery.py` (GCS → BigQuery), `create_master_table.py` (`master_jobs`), `data_quality_checks.py`, `compare_skills_extraction.py` (eval), `inspect_kaggle_csv.py` (dev helper).
- **run_ingestion.py** — CLI for step 1 (dlt → GCS).
- **streamlit_app/** — Browser UI to explore `master_jobs` / `raw_*` in BigQuery (`streamlit run streamlit_app/app.py` or `docker compose up streamlit` → http://localhost:8501).

## Streamlit dashboard (optional)

After raw tables (or `master_jobs`) exist in BigQuery: **`streamlit run streamlit_app/app.py`** from repo root (same `.env` and ADC as ingestion). Or **`docker compose up streamlit`** and open port **8501** (mounts gcloud ADC like the `app` service). **Deploy on GCP (Cloud Run):** [docs/GUIDE_GCP_HOSTING.md](docs/GUIDE_GCP_HOSTING.md).

## Documentation

All docs live under **[docs/](docs/README.md)**. Main guides:

- **[docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)** — High-level story, capstone-style rubric mapping, and what each layer does.
- **[docs/GUIDE_END_TO_END.md](docs/GUIDE_END_TO_END.md)** — Single runbook: Terraform → ingest → BigQuery → optional dbt → Streamlit and quality checks.
- **[docs/GUIDE_GCP_HOSTING.md](docs/GUIDE_GCP_HOSTING.md)** — Cloud Run, Docker/`amd64`, Artifact Registry, **ingress**, IAM, troubleshooting.
- **[docs/GUIDE_DLT_DBT.md](docs/GUIDE_DLT_DBT.md)** — Why **dlt** and **dbt** are used here, how they connect, scenario examples.

**Reference:** [docs/MASTER_TABLE_SPEC.md](docs/MASTER_TABLE_SPEC.md) · [docs/EVALUATE_SKILLS_EXTRACTION.md](docs/EVALUATE_SKILLS_EXTRACTION.md) · [terraform/README.md](terraform/README.md)
