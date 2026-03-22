# Phase 8 — Production hardening & agentic layer

This document ties together **CI**, **tests**, **data quality checks**, **Terraform (secrets + scheduler signal)**, and the **Gemini + whitelisted BigQuery tools** agent.

---

## 1. What was implemented

| Area | Location |
|------|----------|
| **CI** | `.github/workflows/ci.yml` — `ruff`, `pytest`, `dbt parse` |
| **Tests** | `tests/` — schema contract, GCS bucket validation, agent tool guardrails |
| **Data quality** | `scripts/data_quality_checks.py` — raw table counts + `last_ingested`; `--strict` |
| **Secrets (GCP)** | `terraform/phase8.tf` — Secret Manager secret `horizon-pipeline-secrets`, lakehouse SA accessor |
| **Scheduling signal** | Optional `enable_pipeline_scheduler` — Cloud Scheduler → Pub/Sub topic (you add subscriber) |
| **Agentic use case** | `agents/bq_tools.py`, `agents/agentic_runner.py`, `scripts/run_agentic_insights.py` |

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

## 6. Agentic analytics (safe pattern)

The LLM **never** emits raw SQL. It returns JSON choosing one of **`source_row_counts`**, **`top_skills`**, **`posting_volume`**, **`raw_table_health`**. Python executes fixed queries in `agents/bq_tools.py`.

```bash
export GOOGLE_CLOUD_PROJECT=...
export GOOGLE_API_KEY=...    # Gemini (AI Studio)
export DBT_GOLD_DATASET=dbt_gold   # after dbt run
gcloud auth application-default login

python scripts/run_agentic_insights.py "Which source has the most jobs in the gold mart?"
python scripts/run_agentic_insights.py --raw-only
```

**Extend:** add functions in `bq_tools.py`, register in `TOOL_REGISTRY`, document in `TOOL_DESCRIPTIONS`, update the prompt in `agentic_runner.py`.

---

## 7. Suggested “production” run order

1. Ingest + load (orchestrated by your scheduler/subscriber).  
2. `dbt run && dbt test`  
3. `python scripts/data_quality_checks.py --strict --max-age-hours 72`  
4. (Optional) agent or downstream BI on `dbt_gold.mart_jobs_curated`.

---

## 8. Final outcome (project vision)

**Horizon** becomes a **repeatable lakehouse**: landed **raw** data, **dbt** silver/gold, **automated checks**, **secrets in GCP**, and an **agent** that answers questions using **trusted queries**—a base for **agentic** products (chat, reports, alerts) without giving the model arbitrary SQL.
