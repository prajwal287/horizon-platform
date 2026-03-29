# Phase 8 — Production hardening & agentic layer

This document ties together **CI**, **tests**, **data quality checks**, and **Terraform (secrets + scheduler signal)**. Whitelisted BigQuery helpers live in `agents/bq_tools.py` (no LLM in this path).

---

## 1. What was implemented

| Area | Location |
|------|----------|
| **CI** | `.github/workflows/ci.yml` — `ruff`, `pytest`, `dbt parse` |
| **Tests** | `tests/` — schema contract, GCS bucket validation, agent tool guardrails |
| **Data quality** | `scripts/data_quality_checks.py` — raw table counts + `last_ingested`; `--strict` |
| **Secrets (GCP)** | `terraform/phase8.tf` — Secret Manager secret `horizon-pipeline-secrets`, lakehouse SA accessor |
| **Scheduling signal** | Optional `enable_pipeline_scheduler` — Cloud Scheduler → Pub/Sub topic (you add subscriber) |
| **BQ helpers (fixed queries)** | `agents/bq_tools.py` — used by `data_quality_checks.py` and tests |

---

## 2. CI (local or GitHub)

```bash
pip install -r requirements-dev.txt
ruff check ingestion tests agents
pytest
cd dbt && dbt parse --profiles-dir ~/.dbt   # after copying profiles
```

---

## 3. Data quality after each load

```bash
export GOOGLE_CLOUD_PROJECT=...
export BIGQUERY_DATASET=job_market_analysis
python scripts/data_quality_checks.py
python scripts/data_quality_checks.py --strict --max-age-hours 72 --json
```

---

## 4. Secret Manager

After `terraform apply`:

```bash
# Add JSON or .env-style payload (example: Kaggle key) — do not commit real values
echo -n "your-secret-payload" | gcloud secrets versions add horizon-pipeline-secrets --data-file=-
```

Mount or fetch in Cloud Run / Composer using the **lakehouse** service account (already has `secretAccessor` on that secret).

---

## 5. Scheduler tick (optional)

Set in `terraform.tfvars`:

```hcl
enable_pipeline_scheduler = true
pipeline_scheduler_cron   = "0 6 * * *"
```

Apply Terraform. The job **publishes** to your existing Pub/Sub topic `job-stream-input`. You must deploy a **subscriber** (Cloud Run push, Cloud Workflows, Dataflow, etc.) that runs:

`run_ingestion.py` → `load_gcs_to_bigquery.py` → `dbt run`.

---

## 6. Suggested “production” run order

1. Ingest + load (orchestrated by your scheduler/subscriber).  
2. `dbt run && dbt test`  
3. `python scripts/data_quality_checks.py --strict --max-age-hours 72`  
4. (Optional) downstream BI on gold marts (e.g. `mart_jobs_curated`).

---

## 7. Final outcome (project vision)

**Horizon** becomes a **repeatable lakehouse**: landed **raw** data, **dbt** silver/gold, **automated checks**, and **secrets in GCP**—with **whitelisted BigQuery helpers** in `agents/bq_tools.py` for scripts and quality checks (no arbitrary SQL from callers).
