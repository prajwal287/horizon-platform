# End-to-end execution — every step (nothing omitted)

Use this as a **single ordered runbook** from an empty machine through optional dbt, quality checks, dev tooling, Phase 8, and the agent. Replace placeholders (`YOUR_PROJECT_ID`, paths) with your values.

**Conceptual overview & scenarios:** [CODEBASE_END_TO_END_SCENARIOS.md](CODEBASE_END_TO_END_SCENARIOS.md)  
**Alternate narrative runbook (overlap OK):** [COMPLETE_EXECUTION_GUIDE.md](COMPLETE_EXECUTION_GUIDE.md)

---

## Part A — Machine prerequisites

**Step A1 — Install tools**

| Tool | Verify |
|------|--------|
| Python 3.9+ (3.10+ recommended) | `python3 --version` |
| Git | `git --version` |
| Google Cloud SDK | `gcloud --version` |
| Terraform | `terraform -version` |

**Step A2 — Have a GCP project**

- Billing enabled if you will create GCS/BigQuery resources.

**Step A3 — Clone the repository**

```bash
git clone <YOUR_REPO_URL> horizon-platform
cd horizon-platform
pwd
# Expect: run_ingestion.py, requirements.txt, terraform/, dbt/ in this directory.
```

---

## Part B — Python environment (project root only)

**Step B1 — Create and activate a virtual environment** (same folder as `requirements.txt`, **not** inside `terraform/`)

```bash
cd /path/to/horizon-platform
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell: `.venv\Scripts\Activate.ps1`

**Step B2 — Upgrade pip and install runtime dependencies**

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**Done when:** `pip install` completes with no errors.

---

## Part C — Google Cloud authentication and project

**Step C1 — CLI login**

```bash
gcloud auth login
```

**Step C2 — Set the active project** (use the **lowercase project ID**, not the display name)

```bash
gcloud config set project YOUR_PROJECT_ID
```

**Step C3 — Application Default Credentials** (used by Terraform, dlt, BigQuery, GCS, dbt)

```bash
gcloud auth application-default login
```

Optional but recommended to avoid quota warnings:

```bash
gcloud auth application-default set-quota-project YOUR_PROJECT_ID
```

**Step C4 — Verify ADC**

```bash
gcloud auth application-default print-access-token
```

**Done when:** a long token prints (not an error).

---

## Part D — Enable GCP APIs

**Step D1 — Enable services Terraform needs**

```bash
export PROJECT_ID=YOUR_PROJECT_ID
gcloud services enable \
  storage.googleapis.com \
  bigquery.googleapis.com \
  pubsub.googleapis.com \
  iam.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  --project="${PROJECT_ID}"
```

*(If you skip Phase 8, Secret Manager / Scheduler APIs are harmless to enable.)*

---

## Part E — Terraform (infrastructure)

**Step E1 — Configure variables**

```bash
cd /path/to/horizon-platform/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`: set at least `project_id` and `project_name`. Optionally set Phase 8 flags per [PHASE8_PRODUCTION.md](PHASE8_PRODUCTION.md).

**Step E2 — Initialize, plan, apply**

```bash
cd /path/to/horizon-platform/terraform
terraform init
terraform plan
terraform apply
```

Type `yes` when prompted.

**Step E3 — Record outputs** (from `terraform/` after successful apply)

```bash
terraform output -raw gcs_bucket_name
terraform output -raw project_id
terraform output -raw bigquery_dataset_id
```

**Critical:** If you see “No outputs found,” you are in the wrong directory or `apply` did not succeed—**do not** paste warnings into `.env`.

**Alternative from repo root:**

```bash
cd /path/to/horizon-platform
terraform -chdir=terraform output -raw gcs_bucket_name
terraform -chdir=terraform output -raw project_id
terraform -chdir=terraform output -raw bigquery_dataset_id
```

**Done when:** Console shows the new bucket and BigQuery dataset.

---

## Part F — Application `.env`

**Step F1 — Copy example**

```bash
cd /path/to/horizon-platform
cp .env.example .env
```

**Step F2 — Edit `.env`** — minimal:

```bash
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
GCS_BUCKET=YOUR_FULL_BUCKET_NAME_FROM_TERRAFORM
BIGQUERY_DATASET=job_market_analysis
```

**Step F3 — Kaggle** (required for any `--source kaggle_*`)

From [Kaggle → Settings → API](https://www.kaggle.com/settings), set:

```bash
KAGGLE_USERNAME=your_username
KAGGLE_KEY=your_api_key
```

Or place `~/.kaggle/kaggle.json` with mode `600`.

**Step F4 — Recommended taxonomy skills** (Kaggle DE + Hugging Face behavior)

```bash
EXTRACT_SKILLS_TAXONOMY=1
```

**Step F5 — Optional Kaggle LinkedIn row cap**

```bash
# KAGGLE_LINKEDIN_POSTINGS_MAX_ROWS=50000
```

**Step F6 — Load env into your shell** (before Python commands)

```bash
cd /path/to/horizon-platform
source .venv/bin/activate
set -a
source .env
set +a
```

---

## Part G — Pipeline: GCS ingest (Step 1)

**Step G1 — Run dlt → Parquet on GCS**

```bash
cd /path/to/horizon-platform
source .venv/bin/activate
set -a && source .env && set +a
export EXTRACT_SKILLS_TAXONOMY=1   # if you set it in .env, redundant but explicit OK
python3 run_ingestion.py --source all
```

- For a smoke test: `python3 run_ingestion.py --source huggingface`

**Done when:** logs show successful pipeline runs; no tracebacks.

---

## Part H — Pipeline: BigQuery load (Step 2)

**Step H1 — Load Parquet from GCS into `raw_*`**

```bash
python3 scripts/load_gcs_to_bigquery.py --source all
```

Or match Part G: `--source huggingface` only.

**Done when:** script completes; BigQuery has populated `raw_*` tables.

---

## Part I — Python `master_jobs` (optional but common)

**Step I1 — Create clean union view**

```bash
python3 scripts/create_master_table.py --clean
```

**Alternatives:**

- Simple view: `python3 scripts/create_master_table.py`
- Materialized path: see [COMPLETE_EXECUTION_GUIDE.md §12](COMPLETE_EXECUTION_GUIDE.md)

---

## Part J — Verify GCS and BigQuery

**Step J1 — List GCS prefixes**

```bash
set -a && source .env && set +a
gsutil ls "gs://${GCS_BUCKET}/raw/"
```

**Step J2 — List dataset tables**

```bash
bq ls --project_id="${GOOGLE_CLOUD_PROJECT}" "${BIGQUERY_DATASET}"
```

**Step J3 — Sample SQL** (Console or `bq query`)

```sql
SELECT source_id, COUNT(*) AS n
FROM `YOUR_PROJECT_ID.YOUR_DATASET.master_jobs`
GROUP BY 1
ORDER BY n DESC;
```

---

## Part K — dbt (bronze / silver / gold)

**Step K1 — Install dbt adapter** (if not already)

```bash
pip install dbt-bigquery
```

**Step K2 — BigQuery profile**

```bash
mkdir -p ~/.dbt
cp /path/to/horizon-platform/dbt/profiles.yml.example ~/.dbt/profiles.yml
```

Edit `~/.dbt/profiles.yml`: set `project` / `dataset` / `location` to match your GCP project and raw dataset.

**Step K3 — Align `sources.yml` with reality**

Every table listed in `dbt/models/sources.yml` must exist in BigQuery (comment out any raw table you do not load).

**Step K4 — Run dbt**

```bash
export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
export BIGQUERY_DATASET=job_market_analysis
cd /path/to/horizon-platform/dbt
dbt debug
dbt run
dbt test
```

**Step K5 — Verify gold** (example)

```sql
SELECT COUNT(*) FROM `YOUR_PROJECT_ID.dbt_gold.mart_jobs_curated`;
```

**After every data refresh:** repeat **G → H → (I) → K4** in that order.

---

## Part L — Data quality checks

**Step L1 — Non-strict check**

```bash
cd /path/to/horizon-platform
source .venv/bin/activate
set -a && source .env && set +a
python3 scripts/data_quality_checks.py
```

**Step L2 — Strict gate** (for automation)

```bash
python3 scripts/data_quality_checks.py --strict --max-age-hours 72
```

---

## Part M — Phase 6 skills refresh (optional)

**Step M1 — Re-run Kaggle DE (+ optional HF) taxonomy pipeline**

```bash
cd /path/to/horizon-platform
source .venv/bin/activate
set -a && source .env && set +a
chmod +x scripts/run_phase6_kaggle_de_skills.sh
./scripts/run_phase6_kaggle_de_skills.sh
```

With Hugging Face:

```bash
PHASE6_INCLUDE_HF=1 ./scripts/run_phase6_kaggle_de_skills.sh
```

**Step M2 — Reload BigQuery and refresh downstream**

```bash
python3 scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer
# If HF included:
# python3 scripts/load_gcs_to_bigquery.py --source huggingface
python3 scripts/create_master_table.py --clean
cd dbt && dbt run && dbt test
```

---

## Part N — Developer CI parity (optional)

**Step N1 — Dev dependencies**

```bash
pip install -r requirements-dev.txt
```

**Step N2 — Lint and tests**

```bash
cd /path/to/horizon-platform
ruff check ingestion tests agents
pytest
```

**Step N3 — dbt parse** (same as CI)

```bash
cd dbt && dbt parse --profiles-dir ~/.dbt
```

---

## Part O — Docker path (optional alternative to local Python)

**Step O1 — Build**

```bash
cd /path/to/horizon-platform
docker compose build
```

**Step O2 — Host must have ADC**

```bash
gcloud auth application-default login
```

**Step O3 — Run pipeline in container**

```bash
docker compose run --rm app python run_ingestion.py --source all
docker compose run --rm app python scripts/load_gcs_to_bigquery.py --source all
docker compose run --rm app python scripts/create_master_table.py --clean
```

---

## Part P — Phase 8 production extras (optional)

**Step P1 — Apply Terraform** if you changed `enable_pipeline_scheduler` or Secret Manager resources (see `terraform/phase8.tf`).

**Step P2 — Add secret versions** (example)

```bash
echo -n "your-payload" | gcloud secrets versions add horizon-pipeline-secrets --data-file=-
```

**Step P3 — Deploy a Pub/Sub subscriber** if you enabled the scheduler tick — it must orchestrate: ingest → load → `dbt run` (see [PHASE8_PRODUCTION.md](PHASE8_PRODUCTION.md)).

---

## Part Q — Agentic insights (optional)

**Prerequisites:** ADC; `dbt` gold built; Gemini API key.

**Step Q1 — Environment**

```bash
export GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
export BIGQUERY_DATASET=job_market_analysis
export DBT_GOLD_DATASET=dbt_gold
export GOOGLE_API_KEY=your_gemini_key
gcloud auth application-default login
```

**Step Q2 — Run**

```bash
cd /path/to/horizon-platform
source .venv/bin/activate
python3 scripts/run_agentic_insights.py "Which source has the most complete rows in the gold mart?"
```

Raw-only mode:

```bash
python3 scripts/run_agentic_insights.py --raw-only "What are my raw table row counts?"
```

---

## Part R — Final checklist (full stack)

| # | Step | Command / action |
|---|------|------------------|
| 1 | Prerequisites | Python, gcloud, terraform, GCP project |
| 2 | Clone | `git clone` → `cd` project root |
| 3 | Venv + pip | `.venv` + `pip install -r requirements.txt` |
| 4 | gcloud | login, set project, ADC |
| 5 | APIs | `gcloud services enable ...` |
| 6 | Terraform | `init`, `plan`, `apply`; capture outputs |
| 7 | `.env` | `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT`, `BIGQUERY_DATASET`, Kaggle |
| 8 | Ingest | `python3 run_ingestion.py --source all` |
| 9 | Load | `python3 scripts/load_gcs_to_bigquery.py --source all` |
| 10 | Master | `python3 scripts/create_master_table.py --clean` |
| 11 | Verify | `gsutil`, `bq ls`, SQL on `master_jobs` |
| 12 | dbt | `profiles.yml`, `dbt debug`, `dbt run`, `dbt test` |
| 13 | Quality | `python3 scripts/data_quality_checks.py --strict ...` |
| 14 | Optional | Phase 6 script, Docker, Phase 8 secrets/scheduler, agent |

---

## If something fails

See **[COMPLETE_EXECUTION_GUIDE.md §17](COMPLETE_EXECUTION_GUIDE.md)** and **[RUN_SCRIPTS.md](RUN_SCRIPTS.md)** for flags, table names, and common errors (`GCS_BUCKET`, Kaggle, HF 429, etc.).
