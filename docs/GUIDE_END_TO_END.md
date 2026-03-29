# End-to-end execution guide

One path from empty laptop to data in BigQuery and the Streamlit UI. Adapt IDs and regions to your GCP project.

---

## 0. Prerequisites

- Python 3.10+, `gcloud` CLI, Docker (optional but matches repo), Terraform 1.x.
- A GCP project; billing enabled if you create billable resources.
- **Never commit** real `terraform/terraform.tfvars` or `.env` — use the `.example` templates.

---

## 1. Authenticate and configure GCP

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_GCP_PROJECT_ID
```

Enable APIs (or let Terraform/user do it):

```bash
gcloud services enable storage.googleapis.com bigquery.googleapis.com \
  pubsub.googleapis.com iam.googleapis.com --project=YOUR_GCP_PROJECT_ID
```

---

## 2. Infrastructure (Terraform)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set project_id (required), optional names/region
export TF_VAR_project_id=YOUR_GCP_PROJECT_ID   # if you prefer env over file
terraform init
terraform plan
terraform apply
```

Capture outputs:

```bash
terraform output -raw project_id
terraform output -raw gcs_bucket_name
terraform output -raw bigquery_dataset_id
```

---

## 3. Application environment

From repo root:

```bash
cp .env.example .env
# Set GOOGLE_CLOUD_PROJECT, GCS_BUCKET, BIGQUERY_DATASET
# For Kaggle sources: KAGGLE_USERNAME, KAGGLE_KEY
```

---

## 4. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For **dbt** (later steps), install **`dbt-bigquery`** in the same or another venv — see **`dbt/README.md`**. The one-shot script below runs `dbt` on the **host** (`dbt` must be on your `PATH` unless you set `SKIP_DBT=1`).

---

## 5. Batch ingest (dlt → GCS Parquet)

**Docker (matches CI-style isolation):**

```bash
docker compose build
docker compose run --rm app python run_ingestion.py --source all
```

**Or locally:**

```bash
python run_ingestion.py --source all
```

Single sources: `--source huggingface`, `kaggle_data_engineer`, `kaggle_linkedin`, `kaggle_linkedin_skills`.

**All-at-once (orchestrated batch path):** from repo root, after `docker compose build`:

```bash
chmod +x scripts/run_batch_pipeline.sh
./scripts/run_batch_pipeline.sh          # needs `dbt` on PATH for step 4
# or: SKIP_DBT=1 ./scripts/run_batch_pipeline.sh   # then run dbt separately
```

This runs **lake → `raw_*` → `master_jobs` → dbt** in order (see **`docs/PROJECT_OVERVIEW.md`** for rubric mapping).

---

## 6. Load GCS → BigQuery (`raw_*`)

```bash
docker compose run --rm app python scripts/load_gcs_to_bigquery.py --source all
# or: python scripts/load_gcs_to_bigquery.py --source all
```

Verify in BigQuery: dataset `job_market_analysis` (or your `BIGQUERY_DATASET`) contains `raw_*` tables.

---

## 7. Optional: unified `master_jobs` view/table

```bash
python scripts/create_master_table.py --clean
```

Streamlit works best with `master_jobs` when multiple sources are loaded.

Schema reference: [MASTER_TABLE_SPEC.md](MASTER_TABLE_SPEC.md).

---

## 8. Optional: dbt (bronze / silver / gold)

```bash
cd dbt
# profiles.yml from dbt/profiles.yml.example — dataset = job_market_analysis (or yours)
dbt debug
dbt run
dbt test
```

Gold marts land in datasets like **`YOUR_DATASET_dbt_gold`** (BigQuery naming from dbt + profile).  
**Physical optimization:** `mart_jobs_curated` and `mart_posting_volume` build as **partitioned + clustered** BigQuery tables (see model SQL and [GUIDE_DLT_DBT.md](GUIDE_DLT_DBT.md)).  
Concepts: [GUIDE_DLT_DBT.md](GUIDE_DLT_DBT.md).

---

## 9. Streamlit dashboard

```bash
streamlit run streamlit_app/app.py
```

Or: `docker compose up streamlit` → http://localhost:8501

**Cloud Run:** [GUIDE_GCP_HOSTING.md](GUIDE_GCP_HOSTING.md). HTTPS URL: `terraform -chdir=terraform output -raw streamlit_service_uri`. Root [README.md](../README.md) has quick links + rubric.

---

## 10. Data quality (automation-friendly)

```bash
export GOOGLE_CLOUD_PROJECT=YOUR_GCP_PROJECT_ID
export BIGQUERY_DATASET=job_market_analysis
python scripts/data_quality_checks.py
python scripts/data_quality_checks.py --strict --max-age-hours 72
```

---

## 11. Resume mid-flight (no full redo)

- **Only refresh master view:** `python scripts/create_master_table.py --clean`
- **Only reload one source to BQ:** `load_gcs_to_bigquery.py --source <name>` after re-ingesting that source
- **Terraform already applied:** skip §2; ensure `.env` matches outputs

---

## 12. CI (optional)

On push/PR to `main` or `master`, **GitHub Actions** (`.github/workflows/ci.yml`) runs **Ruff**, **pytest**, and a **dbt parse** check against a minimal BigQuery profile (no warehouse credentials required for parse). Use this as a template for stricter data-quality gates or deploy workflows.

---

## Command cheat sheet

| Goal | Command |
|------|---------|
| Full batch chain | `./scripts/run_batch_pipeline.sh` (or `SKIP_DBT=1` …) |
| Ingest all | `python run_ingestion.py --source all` |
| Load all to BQ | `python scripts/load_gcs_to_bigquery.py --source all` |
| Master table | `python scripts/create_master_table.py --clean` |
| dbt | `cd dbt && dbt run && dbt test` |
| Streamlit | `streamlit run streamlit_app/app.py` |
| Quality | `python scripts/data_quality_checks.py --strict --max-age-hours 72` |

---

## Troubleshooting (short)

| Symptom | Check |
|---------|--------|
| dlt cannot write GCS | `GCS_BUCKET`, ADC, bucket IAM |
| BQ load fails | Parquet prefix matches `raw/<source_slug>/`, table names |
| dbt fails on missing table | Comment unused sources in `dbt/models/sources.yml` or load that source |
| Streamlit empty | `master_jobs` or `raw_*` exists; filters not too narrow; `GOOGLE_CLOUD_PROJECT` set |
