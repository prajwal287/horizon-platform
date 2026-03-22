# Phase-by-phase execution checklist

Use this to run the project end-to-end and to know when each phase is **done**. All commands assume **project root**: `horizon-platform/`.

**Full command-by-command run from zero:** [COMPLETE_EXECUTION_GUIDE.md](COMPLETE_EXECUTION_GUIDE.md) (single document; use if anything here feels fragmented).

**Related docs:** [RUN_SCRIPTS.md](RUN_SCRIPTS.md) · [RUN_FROM_SCRATCH.md](RUN_FROM_SCRATCH.md) · [RUN_FROM_INTERMEDIATE.md](RUN_FROM_INTERMEDIATE.md) · [HOW_IT_WORKS.md](HOW_IT_WORKS.md)

---

## Kaggle Data Engineer Job Postings 2023 — how it is handled

| Topic | Detail |
|--------|--------|
| **Source** | Kaggle `lukkardata/data-engineer-job-postings-2023`; ingestion downloads/opens CSV under `data/kaggle/…`. |
| **Mapping** | `Job_details` → `job_title`, `Job_details.1` → `job_description` (see `ingestion/sources/kaggle_data_engineer_2023.py`). |
| **Skills** | With **`EXTRACT_SKILLS_TAXONOMY=1`**, each row runs **taxonomy** (regex over curated tools) on title + description. No LLM. Rows whose text never matches a listed skill keep **`skills` null**—that is expected unless you add LLM or expand `ingestion/config.py` (`DATA_ENGINEER_SKILLS` / aliases). |
| **Other Kaggle pipelines** | LinkedIn-style datasets use their own `skills` columns; this flag only changes **Kaggle DE** and **Hugging Face** loaders. |

---

## Full run from scratch (empty GCP → all sources + taxonomy skills + master)

Do **Phase 0 → 2** first (machine setup, Terraform, `.env` with `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT`, `BIGQUERY_DATASET`, `KAGGLE_USERNAME`, `KAGGLE_KEY`, optional `JOBVEN_API_KEY`). Use a real project root path, not a placeholder.

Then run **ingestion once** with taxonomy enabled so you do **not** need a separate Phase 6 pass for Kaggle DE and Hugging Face:

```bash
cd /path/to/horizon-platform
source .venv/bin/activate
set -a && source .env && set +a   # or export vars manually

export EXTRACT_SKILLS_TAXONOMY=1
python3 run_ingestion.py --source all
python3 scripts/load_gcs_to_bigquery.py --source all
python3 scripts/create_master_table.py --clean
```

**Hugging Face:** with the current code, the same flag uses **`job_type_skills`** to fill `job_description` and backfill **`skills`** when `job_skills` is null.

**If you already ingested without taxonomy:** run `./scripts/run_phase6_kaggle_de_skills.sh` (optionally `PHASE6_INCLUDE_HF=1`) to refresh Kaggle DE and HF only, then reload BigQuery and master—see Phase 6 below.

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

## Phase 6 — Optional: skills taxonomy (Kaggle Data Engineer; Hugging Face optional)

**Why some rows still have null `skills`:** Kaggle DE uses whole-word taxonomy matches only—postings that never mention a listed skill stay null. Hugging Face `lukebarousse/data_jobs` often has null `job_skills`; with `EXTRACT_SKILLS_TAXONOMY=1`, ingestion maps `job_type_skills` into `job_description` and backfills `skills` from title + that text (re-ingest HF after pulling the code change).

**One-shot (from project root, with `.env` or exports set):** loads `.env` if present, then runs ingest → load → clean master.

```bash
./scripts/run_phase6_kaggle_de_skills.sh
```

Also refresh Hugging Face raw + master (same taxonomy flag): `PHASE6_INCLUDE_HF=1 ./scripts/run_phase6_kaggle_de_skills.sh`.

Skip rebuilding `master_jobs`: `SKIP_MASTER=1 ./scripts/run_phase6_kaggle_de_skills.sh`.

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

## Phase 8 — Production hardening (implemented baseline)

See **[PHASE8_PRODUCTION.md](PHASE8_PRODUCTION.md)** for runbooks (quality script, agent, Terraform).

| Item | In repo | Done when |
|------|---------|-----------|
| **Data quality** | `scripts/data_quality_checks.py` | Run after load; use `--strict` in automation |
| **Tests** | `tests/` + `pytest` | `pytest` passes locally / CI |
| **CI** | `.github/workflows/ci.yml` (`ruff`, `pytest`, `dbt parse`) | Green on PR |
| **Scheduling signal** | `terraform/phase8.tf` — optional Scheduler → Pub/Sub | Set `enable_pipeline_scheduler`; add subscriber to run pipeline |
| **Secrets** | Secret Manager secret + IAM for lakehouse SA | Add secret versions via `gcloud`; no keys in git |
| **dbt** | `dbt/` medallion + `dbt test` in CI parse job | `dbt run` after load |
| **Agentic** | `agents/` + `scripts/run_agentic_insights.py` | Gemini + whitelisted BQ tools only |

---

## Quick “am I done?” summary

| Goal | Phases |
|------|--------|
| **Data in BigQuery for analytics** | 0 → 5 |
| **Skills on Kaggle DE + HF (taxonomy) on first full run** | Set `EXTRACT_SKILLS_TAXONOMY=1` during Phase 3 ingest (see **Full run from scratch** above), or run Phase 6 after |
| **Production-ready platform** | 0 → 5 + Phase 8 — see [PHASE8_PRODUCTION.md](PHASE8_PRODUCTION.md) |

---

## If something fails

1. **Ingestion:** Check `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT`, Kaggle env vars, network.
2. **Load:** Confirm Parquet exists under `gs://$GCS_BUCKET/raw/<suffix>/` for that source.
3. **Master:** Run Phase 4 first; master needs at least one `raw_*` table present.

For partial reruns without Terraform, use [RUN_FROM_INTERMEDIATE.md](RUN_FROM_INTERMEDIATE.md).
