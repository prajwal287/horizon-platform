# Phase-by-phase execution checklist

Use this to run the project end-to-end and to know when each phase is **done**. All commands assume **project root**: `horizon-platform/`.

**Related docs:** [RUN_SCRIPTS.md](RUN_SCRIPTS.md) · [RUN_FROM_SCRATCH.md](RUN_FROM_SCRATCH.md) · [RUN_FROM_INTERMEDIATE.md](RUN_FROM_INTERMEDIATE.md) · [HOW_IT_WORKS.md](HOW_IT_WORKS.md)

---

## Phase 0 — Machine prerequisites

| Step | Command / action |
|------|------------------|
| 0.1 | Install **Python 3.9+** |
| 0.2 | Install **gcloud** and **Terraform** (see [terraform/README.md](../terraform/README.md)) |
| 0.3 | Install deps: `pip install -r requirements.txt` |
| 0.4 | (Optional Docker) From root: `docker compose build` |

**Done when**
- [ ] `python3 --version` shows 3.9+
- [ ] `gcloud version` and `terraform -version` work
- [ ] `pip install -r requirements.txt` completes without errors

---

## Phase 1 — GCP project + Terraform (empty project / first time)

| Step | Command / action |
|------|------------------|
| 1.1 | `gcloud auth login` |
| 1.2 | `gcloud config set project YOUR_PROJECT_ID` |
| 1.3 | `gcloud auth application-default login` |
| 1.4 | Enable APIs (replace `YOUR_PROJECT_ID`):<br>`gcloud services enable storage.googleapis.com bigquery.googleapis.com pubsub.googleapis.com iam.googleapis.com --project=YOUR_PROJECT_ID` |
| 1.5 | `cd terraform && cp terraform.tfvars.example terraform.tfvars` — edit `project_id` (and optional region, names) |
| 1.6 | `terraform init` |
| 1.7 | `terraform plan` — review planned resources |
| 1.8 | `terraform apply` — type `yes` |

**Export outputs for later phases** (from `terraform/` after apply):

```bash
export GCS_BUCKET=$(terraform output -raw gcs_bucket_name)
export GOOGLE_CLOUD_PROJECT=$(terraform output -raw project_id)
export BIGQUERY_DATASET=$(terraform output -raw bigquery_dataset_id)
```

**Done when**
- [ ] `terraform apply` succeeded with no errors
- [ ] You have bucket name, project id, dataset id (from outputs or Console)
- [ ] In GCP Console: **GCS bucket**, **BigQuery dataset**, **Pub/Sub topic**, **service account** exist as described in [RUN_FROM_SCRATCH.md](RUN_FROM_SCRATCH.md)

---

## Phase 2 — App environment + secrets

| Step | Command / action |
|------|------------------|
| 2.1 | Copy `.env.example` → `.env` at project root |
| 2.2 | Set `GOOGLE_CLOUD_PROJECT`, `GCS_BUCKET`, `BIGQUERY_DATASET` to match Terraform outputs |
| 2.3 | For Kaggle sources: set `KAGGLE_USERNAME` and `KAGGLE_KEY` (or use `~/.kaggle/kaggle.json`) |
| 2.4 | (Optional) `JOBVEN_API_KEY` for Jobven |
| 2.5 | Confirm ADC still valid: `gcloud auth application-default print-access-token` (should print a token) |

**Docker users:** `docker compose` loads `.env` and mounts host ADC — see [README.md](../README.md).

**Done when**
- [ ] `.env` exists with correct `GCS_BUCKET` and `GOOGLE_CLOUD_PROJECT`
- [ ] Kaggle credentials set if you will run any `--source kaggle_*`
- [ ] ADC works (no auth errors on first GCS/BQ call)

---

## Phase 3 — Step 1: Ingestion → GCS (Parquet)

**Minimal single-source test (recommended first):**

```bash
# From project root, with .env or exports
python3 run_ingestion.py --source kaggle_data_engineer
```

**Full ingest (all sources; Jobven only if `JOBVEN_API_KEY` set):**

```bash
python3 run_ingestion.py --source all
```

**Docker equivalent:**

```bash
docker compose run --rm app python run_ingestion.py --source kaggle_data_engineer
# or --source all
```

**Done when**
- [ ] Command exits **0**
- [ ] Logs show pipeline completed for each source you ran
- [ ] GCS has Parquet under expected prefixes, e.g.:

```bash
gsutil ls gs://$GCS_BUCKET/raw/
# Expect folders like: raw/kaggle_data_engineer_2023/, raw/huggingface_data_jobs/, etc.
```

---

## Phase 4 — Step 2: GCS → BigQuery (`raw_*` tables)

**Match Phase 3 source(s):**

```bash
python3 scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer
# or
python3 scripts/load_gcs_to_bigquery.py --source all
```

**Docker:**

```bash
docker compose run --rm app python scripts/load_gcs_to_bigquery.py --source all
```

**Done when**
- [ ] Command exits **0**
- [ ] BigQuery dataset lists expected tables (names depend on sources loaded):

```bash
bq ls --project_id=$GOOGLE_CLOUD_PROJECT $BIGQUERY_DATASET
```

- [ ] For each loaded source, `raw_*` table has **row count > 0** (Console or `bq query`)

---

## Phase 5 — Master table (`master_jobs`)

**Recommended (clean types + `is_complete`):**

```bash
export GOOGLE_CLOUD_PROJECT=...   # if not already set
export BIGQUERY_DATASET=job_market_analysis   # or your dataset

python3 scripts/create_master_table.py --clean
```

**Materialized table (optional, for heavy queries):**

```bash
python3 scripts/create_master_table.py --clean --create-table    # once
python3 scripts/create_master_table.py --clean --materialize     # each refresh
```

**Done when**
- [ ] Script exits **0**
- [ ] View or table `master_jobs` exists in the dataset
- [ ] Sample query returns rows:

```sql
SELECT source_id, COUNT(*) AS n
FROM `PROJECT.DATASET.master_jobs`
GROUP BY 1
ORDER BY n DESC;
```

---

## Phase 6 — Optional: skills taxonomy (Kaggle Data Engineer only)

| Step | Command |
|------|---------|
| 6.1 | `export EXTRACT_SKILLS_TAXONOMY=1` |
| 6.2 | `python3 run_ingestion.py --source kaggle_data_engineer` |
| 6.3 | `python3 scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer` |
| 6.4 | (Optional) Rebuild master: `python3 scripts/create_master_table.py --clean` |

**Done when**
- [ ] `raw_kaggle_data_engineer_2023` has non-null `skills` for rows where descriptions allow extraction (spot-check in BQ)

---

## Phase 7 — Optional: evaluate skills (taxonomy vs LLM)

See [RUN_SCRIPTS.md](RUN_SCRIPTS.md) and [EVALUATE_SKILLS_EXTRACTION.md](EVALUATE_SKILLS_EXTRACTION.md).

**Quick taxonomy-only (no Gemini):**

```bash
python3 scripts/compare_skills_extraction.py --sample 50 --output comparison_skills.csv --print-metrics --skip-llm
```

**Done when**
- [ ] `comparison_skills.csv` exists and metrics print as expected

---

## Phase 8 — Production hardening (not yet in repo; track manually)

| Item | Suggested action | Done when |
|------|------------------|-----------|
| **Data quality** | Row counts, null rates, freshness per `source_id`; alert on drift | Checks documented + run after each load |
| **Tests** | Add `pytest` for schema mapping, small fixture rows | `pytest` passes in CI |
| **CI** | GitHub Actions (or other): lint + tests on PR | Green pipeline on main |
| **Scheduling** | Cloud Scheduler / Composer / cron calling ingest → load → master | Jobs run on schedule; failures alerted |
| **Secrets** | Move long-lived keys to Secret Manager; workload identity for jobs | No secrets in git; rotation plan |
| **dbt** | When Silver/Gold grows — see [WHEN_TO_USE_DBT.md](WHEN_TO_USE_DBT.md) | dbt project + `dbt test` in CI |

---

## Quick “am I done?” summary

| Goal | Phases |
|------|--------|
| **Data in BigQuery for analytics** | 0 → 5 |
| **Skills on Kaggle DE** | + Phase 6 |
| **Production-ready platform** | 0 → 5 + Phase 8 |

---

## If something fails

1. **Ingestion:** Check `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT`, Kaggle env vars, network.
2. **Load:** Confirm Parquet exists under `gs://$GCS_BUCKET/raw/<suffix>/` for that source.
3. **Master:** Run Phase 4 first; master needs at least one `raw_*` table present.

For partial reruns without Terraform, use [RUN_FROM_INTERMEDIATE.md](RUN_FROM_INTERMEDIATE.md).
