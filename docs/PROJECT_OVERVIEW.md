# Horizon — high-level project overview

This document explains what the codebase does and how it implements a full **end-to-end analytics engineering** pipeline on GCP.

---

## Problem statement

**Business / analyst problem:** Tech job postings are fragmented across multiple **public datasets** (Hugging Face hubs, Kaggle CSVs). Each source uses different columns and freshness. Teams waste time on one-off downloads, inconsistent cleaning, and no single place to compare **volume by provider**, **postings over time**, and **job-level detail** (title, URL, skills) for decisions such as market benchmarking or skills trending.

**What this codebase delivers:** A **repeatable, cloud-first batch pipeline** that (1) lands normalized postings in a **data lake** (Parquet on GCS), (2) loads them into **BigQuery**, (3) applies **dbt** medallion transformations for curated marts, and (4) serves a **Streamlit** dashboard with categorical and temporal views (plus skills, employers, and browse/export).

---

## Dashboard (Streamlit)

The app satisfies a typical “**two tiles**” style requirement:

| Tile | What it shows |
|------|----------------|
| **Categorical** | Bar chart: **job counts by `source_id`** (Hugging Face vs Kaggle sources). |
| **Temporal** | Line chart: **postings over time** (monthly aggregation from `posted_date`). |

Extra **chart** tabs include **top skills by year** and **top hiring companies** (see `streamlit_app/app.py`). There is also **browse**: rows, search, filters, and CSV export.

| Access | How |
|--------|-----|
| **Local** | Repo root: `streamlit run streamlit_app/app.py` → http://localhost:8501 |
| **Cloud Run** | After deploy: `terraform -chdir=terraform output -raw streamlit_service_uri`. Example URL (may differ after redeploy): https://horizon-streamlit-c3eqmsiy5a-uc.a.run.app |

Deploy and refresh the image: [GUIDE_GCP_HOSTING.md](GUIDE_GCP_HOSTING.md). Root [README.md](../README.md) lists the same quick links.

---

## Data pipeline: batch (not stream)

This project is evaluated on **Batch / workflow orchestration**, not on Kafka-style streaming.

| Choice | This project |
|--------|----------------|
| **Stream** (Kafka, Pulsar, Spark Streaming, …) | **Out of scope** — not required when batch is chosen. |
| **Batch** | **Yes.** dlt writes Parquet to GCS (lake); load jobs populate `raw_*` in BigQuery; optional **`scripts/run_batch_pipeline.sh`** chains ingest → load → `master_jobs` → dbt as a linear end-to-end sequence. |

**Automation beyond the script:** Terraform can provision **Pub/Sub** and **Cloud Scheduler** as hooks; you attach **Cloud Run**, **Compute**, or a CI job to run the same commands on a cadence.

---

## Technologies and roles

| Layer | Tool | What it does here |
|-------|------|-------------------|
| **Cloud** | **GCP** | BigQuery, GCS, IAM, optional Cloud Run, Artifact Registry. |
| **IaC** | **Terraform** | Declares bucket, dataset, topic, service accounts, optional Streamlit on Cloud Run. |
| **Ingest / lake** | **dlt** | Moves normalized job rows to **Parquet on GCS** (lake-first). |
| **Warehouse load** | **Python + BigQuery load job** | `load_gcs_to_bigquery.py` — Parquet → `raw_*` tables. |
| **Transform** | **dbt** | Bronze → Silver → Gold. Primary marts **`mart_jobs_curated`** and **`mart_posting_volume`** are **tables** with **partitioning and clustering** (see below). |
| **Dashboard** | **Streamlit** | Explores `master_jobs` or `raw_*`; charts for category + time. |
| **Quality / CI** | **pytest**, **ruff**, **`dbt parse`** | Tests and lint in GitHub Actions (see repo `.github/workflows`). |

If you swap a tool (e.g. Snowflake instead of BigQuery), the *conceptual* flow stays the same: **lake → warehouse → models → BI**.

---

## End-to-end flow (one paragraph)

Sources are read in Python → **dlt** writes **Parquet** to **`gs://…/raw/<source_slug>/`** → **`load_gcs_to_bigquery.py`** creates/rewrites **`raw_*`** in BigQuery → optional **`create_master_table.py`** builds **`master_jobs`** → **`dbt run`** builds bronze/silver/gold → **Streamlit** queries BigQuery for charts and tables.

Details: [GUIDE_END_TO_END.md](GUIDE_END_TO_END.md) · [GUIDE_DLT_DBT.md](GUIDE_DLT_DBT.md).

---

## How common project criteria are met

**These assignment-style requirements are all implemented here.** Ingestion is **batch** (not Kafka/Pulsar); the streaming category is **not applicable** by design.

| Criterion | How this project implements it |
|-----------|--------------------------------|
| **Problem description** | **Problem** section above: fragmented job-posting sources → unified lake → warehouse → dbt → dashboard. |
| **Cloud** | **GCP**: GCS lake, BigQuery warehouse, IAM, optional Cloud Run for Streamlit. Not local-only. |
| **IaC** | **`terraform/`**: bucket, BigQuery dataset, service accounts, Pub/Sub, optional Streamlit—see `terraform/README.md`. |
| **Batch / workflow orchestration** | **`scripts/run_batch_pipeline.sh`**: **(1)** dlt → GCS, **(2)** GCS → BigQuery `raw_*`, **(3)** `master_jobs`, **(4)** dbt run+test. Multi-step pipeline with **data lake** and warehouse load. Terraform can add Scheduler/Pub/Sub hooks; Airflow could wrap the same commands. |
| **Stream** (Kafka, etc.) | **N/A** — **batch** architecture only. |
| **Data warehouse** | **BigQuery** `raw_*`, `master_jobs`, dbt datasets. **Partition + cluster:** `mart_jobs_curated` (by `posted_date`, `source_id`, `content_quality_bucket`); `mart_posting_volume` (by `posting_month`, `source_id`). Raw landing tables are autodetected; gold marts are optimized for typical filters. |
| **Transformations** | **dbt** medallion in **`dbt/`** (bronze → silver → gold). Spark optional for scale (see root README). |
| **Dashboard** | **Streamlit:** categorical + temporal charts; **skills by year**, **top companies**, browse/CSV. |
| **Reproducibility** | **`GUIDE_END_TO_END.md`**, **`.env.example`**, **`terraform/terraform.tfvars.example`**, **`docker-compose.yml`**, **`scripts/run_batch_pipeline.sh`**, **`dbt/README.md`**, CI in **`.github/workflows/ci.yml`**. |

**Extras:** pytest + ruff in CI, `scripts/data_quality_checks.py`, optional Secret Manager in Terraform—see guides.

---

## Repository map (where to look)

| Path | Purpose |
|------|---------|
| `terraform/` | GCP infrastructure. |
| `ingestion/` | dlt pipelines, schema, per-source streams. |
| `run_ingestion.py` | CLI for step 1 (→ dlt → GCS). |
| `scripts/load_gcs_to_bigquery.py` | Step 2 (GCS → `raw_*`). |
| `scripts/create_master_table.py` | Optional `master_jobs` union. |
| `scripts/run_batch_pipeline.sh` | One-shot batch orchestration: lake → raw → master → dbt. |
| `dbt/` | SQL transformations (medallion). |
| `streamlit_app/` | Dashboard code. |
| `agents/bq_tools.py` | Fixed BigQuery helpers for checks/tests. |

---

## Security note

**No real API keys or project IDs** should appear in committed files. Use `.env` (gitignored) and local `terraform.tfvars` (gitignored). See `.env.example` and `terraform/terraform.tfvars.example` for placeholders only.
