# End-to-end codebase functionality — scenarios & examples

This document explains **what the Horizon platform does**, **how the pieces connect**, and **how to think about it through concrete scenarios**. For copy-paste commands in order, use **[E2E_EXECUTION_ALL_STEPS.md](E2E_EXECUTION_ALL_STEPS.md)**.

---

## 1. One-sentence story

**Job postings** are pulled from **Hugging Face**, **Kaggle** (several datasets), and optionally **Jobven**, normalized to one schema, written as **Parquet in GCS**, loaded into **BigQuery `raw_*` tables**, optionally unioned into **`master_jobs`** (Python), then modeled in **dbt** (bronze → silver → gold), with **tests, CI, data-quality checks**, and a **Gemini agent** that only runs **whitelisted BigQuery queries**.

---

## 2. Logical architecture (layers)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SOURCES                                                                     │
│  HF data_jobs · Kaggle CSV/API · Jobven API (24h US jobs)                    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ Python streams → RawJobRow
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  INGESTION (dlt)                                                             │
│  run_ingestion.py → ingestion/pipelines/common.py → Parquet on GCS           │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ gs://bucket/raw/<source>/
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  WAREHOUSE LOAD                                                              │
│  load_gcs_to_bigquery.py → raw_huggingface_* , raw_kaggle_* , raw_jobven_*   │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
          ┌─────────────────────────┴─────────────────────────┐
          ▼                                                   ▼
┌──────────────────────┐                         ┌──────────────────────────┐
│  PYTHON MASTER       │                         │  dbt (recommended)        │
│  create_master_table │                         │  bronze → silver → gold   │
│  view master_jobs    │                         │  mart_jobs_curated, etc.   │
└──────────────────────┘                         └──────────────────────────┘
          │                                                   │
          └─────────────────────────┬─────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  CONSUMPTION                                                                 │
│  BigQuery SQL · BI tools · scripts/data_quality_checks.py · agents (Gemini)   │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Infrastructure (Terraform):** GCS bucket, BigQuery dataset, Pub/Sub topic, lakehouse service account, IAM, Secret Manager secret, optional Cloud Scheduler tick → Pub/Sub.

---

## 3. Repository map (what lives where)

| Path | Purpose |
|------|---------|
| **`run_ingestion.py`** | CLI: Step 1 — dlt → GCS. |
| **`ingestion/schema.py`** | Canonical row shape (`RawJobRow`, `JOBS_COLUMNS`). |
| **`ingestion/config.py`** | Env config, GCS validation helpers, skills taxonomy lists. |
| **`ingestion/pipelines/common.py`** | Shared dlt `run_pipeline()` (replace, Parquet). |
| **`ingestion/pipelines/run_*.py`** | One entrypoint per source (HF, Kaggle, Jobven). |
| **`ingestion/sources/*.py`** | Read source data → yield batches of dicts. |
| **`ingestion/skills_extraction.py`** | Taxonomy (and optional LLM helpers for eval scripts). |
| **`scripts/load_gcs_to_bigquery.py`** | Step 2 — Parquet → `raw_*`. |
| **`scripts/create_master_table.py`** | Union `raw_*` → `master_jobs` view/table. |
| **`scripts/data_quality_checks.py`** | Post-load row counts / freshness on raw tables. |
| **`scripts/run_agentic_insights.py`** | Gemini + safe BQ tools (agentic). |
| **`scripts/run_phase6_kaggle_de_skills.sh`** | Kaggle DE (+ optional HF) taxonomy skills refresh. |
| **`dbt/`** | SQL models: bronze views, silver union/dedupe, gold marts. |
| **`agents/`** | Whitelisted BigQuery tools + Gemini planner/summarizer. |
| **`terraform/`** | GCP resources + Phase 8 Secret Manager / optional Scheduler. |
| **`.github/workflows/ci.yml`** | Ruff, pytest, `dbt parse`. |
| **`tests/`** | Pytest contract tests. |

---

## 4. Data shape (canonical job row)

Every pipeline outputs the same logical columns (see `ingestion/schema.py`):

- **Identity:** `source_id`, `source_name`  
- **Job:** `job_title`, `job_description`, `company_name`, `location`, `posted_date`, `job_url`  
- **Enrichment:** `skills` (often array or JSON in BQ), `salary_info`  
- **Lineage:** `ingested_at`  

**Example** (conceptual JSON after `to_load_dict()`):

```json
{
  "source_id": "kaggle_data_engineer_2023",
  "source_name": "Kaggle Data Engineer Job Postings 2023",
  "job_title": "Senior Data Engineer",
  "job_description": "We use Python, SQL, and BigQuery...",
  "company_name": "Acme",
  "location": "Remote",
  "posted_date": "2023-04-01",
  "job_url": null,
  "skills": ["Python", "SQL", "BigQuery"],
  "salary_info": "120000 USD",
  "ingested_at": "2026-03-22T12:00:00"
}
```

---

## 5. Source-specific behavior (examples)

| Source | CLI `--source` | How data arrives | Notes |
|--------|----------------|------------------|--------|
| Hugging Face | `huggingface` | `datasets.load_dataset("lukebarousse/data_jobs")` | Domain + date filters; `job_type_skills` mapped to description when taxonomy on. |
| Kaggle DE | `kaggle_data_engineer` | Kaggle API → CSV under `data/kaggle/...` | `EXTRACT_SKILLS_TAXONOMY=1` fills skills from title + description. |
| Kaggle LinkedIn postings | `kaggle_linkedin` | Kaggle CSV | Optional `KAGGLE_LINKEDIN_POSTINGS_MAX_ROWS` cap. |
| Kaggle LinkedIn skills | `kaggle_linkedin_skills` | Kaggle CSV | Native skills columns when present. |
| Jobven | `jobven` | REST API, `postedAfter` = 24h | Needs `JOBVEN_API_KEY`; optional `JOBVEN_MAX_PAGES`, `JOBVEN_QUERY`. |

**`--source all`** runs every pipeline where credentials exist (Jobven skipped if no API key).

---

## 6. Scenarios (walkthroughs)

### Scenario A — First analytics dataset (minimal)

**Goal:** Prove the pipe with one source.

1. Terraform + `.env` with `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT`.  
2. `python3 run_ingestion.py --source huggingface`  
3. `python3 scripts/load_gcs_to_bigquery.py --source huggingface`  
4. In BigQuery: `SELECT COUNT(*) FROM raw_huggingface_data_jobs`.

**Outcome:** One raw table populated.

---

### Scenario B — Full multi-source lake + Python master

**Goal:** All sources you care about + single view for SQL.

1. Set Kaggle (and optional Jobven) credentials in `.env`.  
2. `export EXTRACT_SKILLS_TAXONOMY=1`  
3. `python3 run_ingestion.py --source all`  
4. `python3 scripts/load_gcs_to_bigquery.py --source all`  
5. `python3 scripts/create_master_table.py --clean`  

**Example query:**

```sql
SELECT source_id, COUNT(*) AS n
FROM `YOUR_PROJECT.job_market_analysis.master_jobs`
GROUP BY 1;
```

**Outcome:** `master_jobs` with `is_complete` for filtering.

---

### Scenario C — dbt medallion (bronze / silver / gold)

**Goal:** Deduped mart and aggregates for BI.

**Prerequisite:** All `raw_*` tables referenced in `dbt/models/sources.yml` exist (remove Jobven from sources if unused).

1. After load: `cd dbt && dbt run && dbt test`  
2. Query gold:

```sql
SELECT * FROM `YOUR_PROJECT.dbt_gold.mart_jobs_curated` WHERE is_complete LIMIT 20;
SELECT * FROM `YOUR_PROJECT.dbt_gold.mart_skill_demand` LIMIT 20;
```

**Outcome:** `mart_jobs_curated`, `mart_posting_volume`, `mart_skill_demand`, `mart_cross_source_urls`.

---

### Scenario D — Refresh only Kaggle DE skills

**Goal:** Re-ingest DE with taxonomy without redoing everything.

1. `./scripts/run_phase6_kaggle_de_skills.sh`  
   - Or `PHASE6_INCLUDE_HF=1` to refresh Hugging Face too.  
2. Reload BigQuery and rebuild master/dbt as you prefer.

---

### Scenario E — Data quality gate after load

**Goal:** Fail a job if raw tables are empty or stale.

```bash
python3 scripts/data_quality_checks.py --strict --max-age-hours 72
```

**Outcome:** Exit code `0` or `1` for automation (e.g. CI or Composer).

---

### Scenario F — Agentic question (“talk to the data” safely)

**Goal:** Natural language without arbitrary SQL from the model.

**Prerequisite:** ADC for BigQuery, `GOOGLE_API_KEY` for Gemini, dbt gold built for mart tools.

```bash
python3 scripts/run_agentic_insights.py "What are the top skills in our gold mart?"
```

The model picks one of: `source_row_counts`, `top_skills`, `posting_volume`, `raw_table_health`. Only those functions run fixed SQL.

---

### Scenario G — Production hardening (Phase 8)

**Goal:** Secrets + schedule signal + CI.

1. `terraform apply` (includes Secret Manager; optional `enable_pipeline_scheduler = true`).  
2. Add secret versions via `gcloud secrets versions add ...`.  
3. GitHub Actions runs on PR: lint, tests, `dbt parse`.  
4. You still implement a **Pub/Sub subscriber** (Cloud Run / Workflows) to run ingest → load → dbt on each tick.

Details: [PHASE8_PRODUCTION.md](PHASE8_PRODUCTION.md).

---

## 7. Idempotency & replace semantics

- **dlt** uses **`replace`** for the jobs resource: re-running ingestion overwrites Parquet for that source prefix.  
- **BigQuery load** uses **WRITE_TRUNCATE**: each load replaces the whole `raw_*` table.  
- **Dedup in dbt silver** reduces duplicate logical jobs within a source using a fingerprint + latest `ingested_at`.  

So: **re-runs do not append duplicate raw rows by default**; they refresh snapshots.

---

## 8. Related docs

| Topic | Document |
|--------|-----------|
| Deeper step-1/2 mechanics | [HOW_IT_WORKS.md](HOW_IT_WORKS.md) |
| Command reference & options | [RUN_SCRIPTS.md](RUN_SCRIPTS.md) |
| Terraform & dlt concepts | [RUN_FROM_SCRATCH.md](RUN_FROM_SCRATCH.md) |
| Ordered execution (every step) | [E2E_EXECUTION_ALL_STEPS.md](E2E_EXECUTION_ALL_STEPS.md) |
| dbt layout | [DBT_INTEGRATION.md](DBT_INTEGRATION.md) |
| Phase 8 + agent | [PHASE8_PRODUCTION.md](PHASE8_PRODUCTION.md) |
