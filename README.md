# Horizon — Job market data lakehouse

End-to-end **data engineering** project: unify Hugging Face + Kaggle job postings in **GCP** using **dlt → GCS (data lake) → BigQuery (warehouse) → dbt (medallion) → Streamlit (dashboard)**. **Terraform** provisions infrastructure; **batch** orchestration is scripted end-to-end.

---

## Quick access

| What | Where |
|------|--------|
| **Run the dashboard locally** | From repo root: `streamlit run streamlit_app/app.py` → [http://localhost:8501](http://localhost:8501) (needs BigQuery data + `gcloud auth application-default login`). |
| **Hosted dashboard (Cloud Run)** | **Always get the current URL from Terraform** (URL changes if you recreate the service): `terraform -chdir=terraform output -raw streamlit_service_uri` |
| **Example Cloud Run URL** (demo; *your* URL comes from the command above) | [https://horizon-streamlit-c3eqmsiy5a-uc.a.run.app](https://horizon-streamlit-c3eqmsiy5a-uc.a.run.app) |

Deploy or refresh hosting: **[docs/GUIDE_GCP_HOSTING.md](docs/GUIDE_GCP_HOSTING.md)** (build `Dockerfile.streamlit`, push to Artifact Registry, `enable_streamlit_cloud_run = true`, `terraform apply`, then update the service after code changes).

---

## Problem this project solves

**Situation:** Job postings are scattered across **different public datasets** (Hugging Face, Kaggle) with inconsistent schemas.

**Pain:** No single, repeatable place to **land** data in a lake, **load** it into a warehouse, **transform** it for analysis, and **explore** trends (by source, over time, skills, employers).

**Outcome:** This repo implements a **cloud-first batch pipeline** plus a **browser dashboard** so reviewers can reproduce **ingestion → lake → BigQuery → dbt → UI** without one-off notebooks only.

---

## Architecture (60 seconds)

1. **dlt** writes **Parquet** to **GCS** under `gs://<bucket>/raw/<source_slug>/`.
2. **`scripts/load_gcs_to_bigquery.py`** loads Parquet into **BigQuery** `raw_*` tables.
3. **`scripts/create_master_table.py`** (optional) builds **`master_jobs`** across sources.
4. **dbt** (`dbt/`): bronze → silver → gold (partitioned/clustered marts where it matters).
5. **Streamlit** (`streamlit_app/`) reads BigQuery: **compare sources**, **volume over time**, **top skills by year**, **top companies**, **browse/export**.

**One-shot batch chain:** `./scripts/run_batch_pipeline.sh` (set `SKIP_DBT=1` if `dbt` is not on your PATH yet). **Full runbook:** [docs/GUIDE_END_TO_END.md](docs/GUIDE_END_TO_END.md).

---

## Course / peer evaluation criteria — how this repo maps

Below is the same rubric many capstone and peer-review sheets ask for. **This project targets the “batch” path** (not Kafka streaming). Streaming rows are marked **N/A**.

| Criterion | Points | How Horizon addresses it |
|-----------|--------|---------------------------|
| **Problem description** | **4** | Clear **who/what/why** above and in [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md): fragmented sources → unified lakehouse + dashboard. |
| **Cloud** | **4** | **GCP**: GCS, BigQuery, IAM, optional Cloud Run — not local-only. |
| **IaC** | **4** (with Cloud) | **`terraform/`**: bucket, dataset, Pub/Sub, service accounts, optional Streamlit — see [terraform/README.md](terraform/README.md). |
| **Batch / workflow orchestration** | **4** | **`scripts/run_batch_pipeline.sh`**: multiple ordered steps—**lake** (dlt → GCS) → **warehouse** (`raw_*`) → **`master_jobs`** → **dbt**. |
| **Stream** (Kafka, etc.) | **N/A** | **Batch** is the chosen path; streaming is not claimed. |
| **Data warehouse** | **4** | **BigQuery** `raw_*`, `master_jobs`, dbt datasets. **Partition + cluster** on **`mart_jobs_curated`** and **`mart_posting_volume`** (see [docs/GUIDE_DLT_DBT.md](docs/GUIDE_DLT_DBT.md)). |
| **Transformations** | **4** | **dbt** medallion (not ad-hoc SQL only): `dbt/` bronze → silver → gold. |
| **Dashboard** | **4** | **Streamlit** with **≥2** chart tiles: **categorical** (counts by `source_id`) + **temporal** (monthly volume); plus skills-by-year, top companies, browse/CSV. |
| **Reproducibility** | **4** | **`.env.example`**, **`terraform/terraform.tfvars.example`**, **[docs/GUIDE_END_TO_END.md](docs/GUIDE_END_TO_END.md)**, Docker Compose, **dbt** profile example, CI (`.github/workflows/ci.yml`). |

**Story + rubric detail:** [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md).

---

## Running the pipeline (summary)

**Prereqs:** `gcloud auth application-default login`, `terraform apply` (or existing GCP resources), `.env` from `.env.example`.

**Docker (recommended):**

```bash
docker compose build
docker compose run --rm app python run_ingestion.py --source all
docker compose run --rm app python scripts/load_gcs_to_bigquery.py --source all
docker compose run --rm app python scripts/create_master_table.py --clean
```

**dbt** (on host with venv): `export GOOGLE_CLOUD_PROJECT=...` → copy `dbt/profiles.yml.example` to `~/.dbt/profiles.yml` → `cd dbt && dbt run && dbt test` — see [dbt/README.md](dbt/README.md).

**Outputs:** `terraform -chdir=terraform output -raw gcs_bucket_name` · `bigquery_dataset_id` · `streamlit_service_uri` (if Cloud Run enabled).

## Project layout

- **terraform/** — GCP IaC (GCS, BigQuery, Pub/Sub, optional Cloud Run).
- **ingestion/** — dlt pipelines → Parquet on GCS.
- **scripts/** — load to BigQuery, `master_jobs`, `run_batch_pipeline.sh`, quality checks.
- **dbt/** — SQL transformations (medallion).
- **streamlit_app/** — Dashboard.

## Documentation index

| Doc | Purpose |
|-----|---------|
| [docs/README.md](docs/README.md) | Doc hub |
| [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | Narrative for peers + rubric |
| [docs/GUIDE_END_TO_END.md](docs/GUIDE_END_TO_END.md) | Step-by-step runbook |
| [docs/GUIDE_GCP_HOSTING.md](docs/GUIDE_GCP_HOSTING.md) | Cloud Run, image push, IAM |
| [docs/GUIDE_DLT_DBT.md](docs/GUIDE_DLT_DBT.md) | dlt vs dbt, partitions |

**Reference:** [docs/MASTER_TABLE_SPEC.md](docs/MASTER_TABLE_SPEC.md) · [docs/EVALUATE_SKILLS_EXTRACTION.md](docs/EVALUATE_SKILLS_EXTRACTION.md)
