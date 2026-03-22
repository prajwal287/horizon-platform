# Complete execution guide (from scratch)

Single runbook: **machine setup → GCP + Terraform → Python env → ingest (dlt → GCS) → BigQuery → master view**. Copy commands in order; replace placeholders with your values.

**Repository root** in all examples: the folder that contains `run_ingestion.py`, `requirements.txt`, and `terraform/` (clone path is yours to choose).

---

## Table of contents

1. [What you get at the end](#1-what-you-get-at-the-end)
2. [Prerequisites](#2-prerequisites)
3. [Clone repo and open a terminal at project root](#3-clone-repo-and-open-a-terminal-at-project-root)
4. [Python virtual environment and dependencies](#4-python-virtual-environment-and-dependencies)
5. [Google Cloud: login, project, Application Default Credentials](#5-google-cloud-login-project-application-default-credentials)
6. [Enable GCP APIs](#6-enable-gcp-apis)
7. [Terraform: create bucket, BigQuery dataset, Pub/Sub, service account](#7-terraform-create-bucket-bigquery-dataset-pubsub-service-account)
8. [Application `.env` file](#8-application-env-file)
9. [Kaggle API credentials (for Kaggle sources)](#9-kaggle-api-credentials-for-kaggle-sources)
10. [End-to-end pipeline (recommended: all sources + taxonomy skills)](#10-end-to-end-pipeline-recommended-all-sources--taxonomy-skills)
11. [Verify GCS and BigQuery](#11-verify-gcs-and-bigquery)
12. [Master table options (view vs materialized)](#12-master-table-options-view-vs-materialized)
13. [Re-run skills only (Kaggle DE + optional Hugging Face)](#13-re-run-skills-only-kaggle-de--optional-hugging-face)
14. [Single-source or smaller test runs](#14-single-source-or-smaller-test-runs)
15. [Run with Docker (optional)](#15-run-with-docker-optional)
16. [Sources, tables, and required secrets](#16-sources-tables-and-required-secrets)
17. [Troubleshooting](#17-troubleshooting)
18. [After you are done](#18-after-you-are-done)

---

## 1. What you get at the end

- **GCS:** Parquet files under `gs://<bucket>/raw/<source>/`.
- **BigQuery:** `raw_*` tables in dataset `job_market_analysis` (or the name Terraform used).
- **BigQuery:** `master_jobs` view (or table) unioning loaded raw tables, optionally with `--clean` (typed columns + `is_complete`).

---

## 2. Prerequisites

| Requirement | Check | Install (examples) |
|-------------|--------|---------------------|
| **Python 3.9+** | `python3 --version` | [python.org](https://www.python.org/downloads/) or `brew install python@3.11` |
| **Google Cloud SDK** | `gcloud --version` | [Install gcloud](https://cloud.google.com/sdk/docs/install) or `brew install google-cloud-sdk` |
| **Terraform** | `terraform -version` | [Install Terraform](https://developer.hashicorp.com/terraform/install) or `brew install terraform` |
| **GCP project** | Project ID in Console | [Create project](https://console.cloud.google.com/projectcreate) |
| **Git** | `git --version` | `brew install git` |

You need a **billing-enabled** GCP project if APIs create billable resources (GCS, BigQuery).

---

## 3. Clone repo and open a terminal at project root

```bash
git clone <YOUR_REPO_URL> horizon-platform
cd horizon-platform
pwd
# You must see run_ingestion.py and terraform/ in this directory.
```

## 4. Python virtual environment and dependencies

Always create the venv **in the project root** (same folder as `requirements.txt`), not inside `terraform/`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Windows (PowerShell):** `.venv\Scripts\Activate.ps1` instead of `source .venv/bin/activate`.

**Done when:** `pip install -r requirements.txt` finishes with no errors.

---

## 5. Google Cloud: login, project, Application Default Credentials

Run in any terminal (venv optional for these commands).

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login
```

Replace `YOUR_PROJECT_ID` with your real GCP project ID (not the display name).

**Why two logins:** `gcloud auth login` is for the gcloud CLI. `application-default login` creates credentials that **Terraform** and **Python** (dlt, BigQuery, GCS) use automatically.

**Done when:**

```bash
gcloud auth application-default print-access-token
```

prints a long token string (not an error).

---

## 6. Enable GCP APIs

Terraform needs these APIs on your project:

```bash
export PROJECT_ID=YOUR_PROJECT_ID
gcloud services enable \
  storage.googleapis.com \
  bigquery.googleapis.com \
  pubsub.googleapis.com \
  iam.googleapis.com \
  --project="${PROJECT_ID}"
```

---

## 7. Terraform: create bucket, BigQuery dataset, Pub/Sub, service account

All commands below assume you start from **project root**, then work in `terraform/`.

### 7.1 Configure variables

```bash
cd /path/to/horizon-platform/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and set at least:

```hcl
project_id   = "YOUR_PROJECT_ID"
project_name = "Your project display name"
```

Save the file. Optional overrides (region, bucket suffix, dataset id) are commented in `terraform.tfvars.example`.

### 7.2 Initialize, plan, apply

```bash
cd /path/to/horizon-platform/terraform
terraform init
terraform plan
terraform apply
```

When prompted, type `yes`.

### 7.3 Capture outputs for `.env`

Run these **from the `terraform/` directory** after a successful `terraform apply`. If you run `terraform output` in the wrong folder or before any apply, you get “No outputs found”—**do not** paste that warning into `GCS_BUCKET` (it will break `load_gcs_to_bigquery.py` with a cryptic GCS error).

Still in `terraform/`:

```bash
terraform output -raw gcs_bucket_name
terraform output -raw project_id
terraform output -raw bigquery_dataset_id
```

Copy those values into your `.env` (next section). Or export in the shell:

```bash
export GCS_BUCKET=$(terraform output -raw gcs_bucket_name)
export GOOGLE_CLOUD_PROJECT=$(terraform output -raw project_id)
export BIGQUERY_DATASET=$(terraform output -raw bigquery_dataset_id)
```

**Alternative from project root** (without `cd terraform`):

```bash
cd /path/to/horizon-platform
export GCS_BUCKET=$(terraform -chdir=terraform output -raw gcs_bucket_name)
export GOOGLE_CLOUD_PROJECT=$(terraform -chdir=terraform output -raw project_id)
export BIGQUERY_DATASET=$(terraform -chdir=terraform output -raw bigquery_dataset_id)
```

**Done when:** `terraform apply` succeeded; Console shows the new GCS bucket and BigQuery dataset.

---

## 8. Application `.env` file

From **project root**:

```bash
cd /path/to/horizon-platform
cp .env.example .env
```

Edit `.env`. Minimal content (use values from Terraform outputs):

```bash
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
GCS_BUCKET=YOUR_FULL_BUCKET_NAME
BIGQUERY_DATASET=job_market_analysis

# Kaggle — required if you use any --source kaggle_*
KAGGLE_USERNAME=your_kaggle_username
KAGGLE_KEY=your_kaggle_api_key

# Recommended for Kaggle Data Engineer + Hugging Face taxonomy skills
EXTRACT_SKILLS_TAXONOMY=1

# Optional — only if you use Jobven
# JOBVEN_API_KEY=your_jobven_key
```

`run_ingestion.py` loads `.env` automatically if `python-dotenv` is installed (included in `requirements.txt`).

---

## 9. Kaggle API credentials (for Kaggle sources)

**Option A — environment variables (matches `.env` above):**  
[Kaggle → Settings → API → Create New Token](https://www.kaggle.com/settings). Use `username` and `key` from `kaggle.json` as `KAGGLE_USERNAME` and `KAGGLE_KEY`.

**Option B — file:**

```bash
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

If this file exists, you may omit `KAGGLE_USERNAME` / `KAGGLE_KEY` in `.env` for some flows; the Phase 6 helper script still prefers explicit env vars—using `.env` is simplest.

---

## 10. End-to-end pipeline (recommended: all sources + taxonomy skills)

Activate the venv and run from **project root**.

```bash
cd /path/to/horizon-platform
source .venv/bin/activate
set -a
source .env
set +a
```

**Step A — Ingest all sources to GCS (Parquet)**

`--source all` runs: Hugging Face, Kaggle Data Engineer, Kaggle LinkedIn, Kaggle LinkedIn Skills, and Jobven **only if** `JOBVEN_API_KEY` is set.

```bash
export EXTRACT_SKILLS_TAXONOMY=1
python3 run_ingestion.py --source all
```

**Step B — Load GCS Parquet into BigQuery**

```bash
python3 scripts/load_gcs_to_bigquery.py --source all
```

**Step C — Create / update `master_jobs` (recommended: clean view)**

```bash
python3 scripts/create_master_table.py --clean
```

**Done when:** no Python tracebacks; BigQuery has `raw_*` tables with row counts and a `master_jobs` view.

---

## 11. Verify GCS and BigQuery

```bash
source .venv/bin/activate
set -a && source .env && set +a

gsutil ls "gs://${GCS_BUCKET}/raw/"
```

Expect folders such as `raw/huggingface_data_jobs/`, `raw/kaggle_data_engineer_2023/`, etc.

```bash
bq ls --project_id="${GOOGLE_CLOUD_PROJECT}" "${BIGQUERY_DATASET}"
```

**Sample SQL** (Console or `bq query`):

```sql
SELECT source_id, COUNT(*) AS n
FROM `YOUR_PROJECT_ID.YOUR_DATASET.master_jobs`
GROUP BY 1
ORDER BY n DESC;
```

Replace `YOUR_PROJECT_ID` and `YOUR_DATASET` with real values.

---

## 12. Master table options (view vs materialized)

| Goal | Commands |
|------|----------|
| **Clean view (default recommendation)** | `python3 scripts/create_master_table.py --clean` |
| **Simple union view (no `is_complete`)** | `python3 scripts/create_master_table.py` |
| **Materialized table (create once, then refresh)** | `python3 scripts/create_master_table.py --clean --create-table` then `python3 scripts/create_master_table.py --clean --materialize` |

---

## 13. Re-run skills only (Kaggle DE + optional Hugging Face)

If you already loaded data but need to refresh **taxonomy skills** and optionally **Hugging Face** without redoing Terraform:

```bash
cd /path/to/horizon-platform
source .venv/bin/activate
set -a && source .env && set +a

chmod +x scripts/run_phase6_kaggle_de_skills.sh
./scripts/run_phase6_kaggle_de_skills.sh
```

Also refresh Hugging Face in the same run:

```bash
PHASE6_INCLUDE_HF=1 ./scripts/run_phase6_kaggle_de_skills.sh
```

Skip rebuilding master:

```bash
SKIP_MASTER=1 ./scripts/run_phase6_kaggle_de_skills.sh
```

**Shell scripts must use LF line endings on macOS/Linux.** If you see `env: bash\r: No such file or directory`, convert the script to Unix line endings (the repo uses `.gitattributes` for `*.sh`).

---

## 14. Single-source or smaller test runs

Same `.env` and venv; pick one source for ingest and load:

```bash
source .venv/bin/activate
set -a && source .env && set +a
export EXTRACT_SKILLS_TAXONOMY=1

python3 run_ingestion.py --source huggingface
python3 scripts/load_gcs_to_bigquery.py --source huggingface

python3 run_ingestion.py --source kaggle_data_engineer
python3 scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer
```

Then refresh master:

```bash
python3 scripts/create_master_table.py --clean
```

---

## 15. Run with Docker (optional)

From project root:

```bash
docker compose build
```

Ensure `.env` exists and ADC works on the host (`gcloud auth application-default login`). Then:

```bash
docker compose run --rm app python run_ingestion.py --source all
docker compose run --rm app python scripts/load_gcs_to_bigquery.py --source all
docker compose run --rm app python scripts/create_master_table.py --clean
```

Set `EXTRACT_SKILLS_TAXONOMY=1` in `.env` before `docker compose run` if you want taxonomy skills in the container.

---

## 16. Sources, tables, and required secrets

| `--source` | BigQuery table (approx.) | Required credentials |
|------------|--------------------------|----------------------|
| `huggingface` | `raw_huggingface_data_jobs` | None; HF dataset is public |
| `kaggle_data_engineer` | `raw_kaggle_data_engineer_2023` | `KAGGLE_USERNAME` + `KAGGLE_KEY` (or `~/.kaggle/kaggle.json`) |
| `kaggle_linkedin` | `raw_kaggle_linkedin_postings` | Kaggle |
| `kaggle_linkedin_skills` | `raw_kaggle_linkedin_jobs_skills_2024` | Kaggle |
| `jobven` | `raw_jobven_jobs` | `JOBVEN_API_KEY` (optional; omitted from `all` if unset) |

**`EXTRACT_SKILLS_TAXONOMY=1`** affects **Kaggle Data Engineer** and **Hugging Face** loaders only (taxonomy from title/description text; see `ingestion/config.py`).

---

## 17. Troubleshooting

| Symptom | What to check |
|---------|----------------|
| `GCS_BUCKET` missing, invalid, or “Terraform warning text” | Put **only** the bucket string in `.env` (one line): `cd terraform && terraform output -raw gcs_bucket_name` after `apply`. Load `.env`: `set -a; source .env; set +a`. Never paste “No outputs found” warnings into `GCS_BUCKET`. |
| `GOOGLE_CLOUD_PROJECT` / `GCP_PROJECT` missing | Same as above |
| Terraform permission errors | `gcloud auth login`; account has Owner/Editor or sufficient IAM on project |
| BigQuery load: no Parquet files | Run `run_ingestion.py` first; `gsutil ls gs://$GCS_BUCKET/raw/...` |
| Kaggle 401 / download failed | `KAGGLE_KEY` correct; or valid `~/.kaggle/kaggle.json` |
| `pip` / `requirements.txt` not found | Current directory is **project root**, not `terraform/` |
| Docker auth errors | Host must run `gcloud auth application-default login`; see `README.md` |
| Hugging Face logs show **404** on `data_jobs.py` / `dataset_infos.json` | Normal: the client probes legacy paths; Parquet-based datasets 404 those URLs and continue. Only worry on tracebacks, **401/403**, or **429** (then set `HF_TOKEN` from [HF tokens](https://huggingface.co/settings/tokens)). |
| **google-auth** / Python **3.9** FutureWarning | Upgrade to **Python 3.10+** when practical; `pip install -U google-auth`. |

---

## 18. After you are done

- Query **`master_jobs`** (or filter `WHERE is_complete`) for analytics.
- For scheduling, monitoring, CI, and dbt: see [EXECUTION_CHECKLIST.md](EXECUTION_CHECKLIST.md) Phase 8 and [WHEN_TO_USE_DBT.md](WHEN_TO_USE_DBT.md).
- Conceptual flow: [HOW_IT_WORKS.md](HOW_IT_WORKS.md).

---

*This guide is the canonical step-by-step command list for a full scratch run. Terraform details and GCP concepts are also in [terraform/README.md](../terraform/README.md) and [RUN_FROM_SCRATCH.md](RUN_FROM_SCRATCH.md).*
