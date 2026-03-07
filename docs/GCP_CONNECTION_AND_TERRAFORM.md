# GCP Connection from Scratch + Run Terraform

Do these in order. Run from **project root** unless noted.

---

## Kaggle handshake (do this first to verify Kaggle)

Before or after GCP setup, confirm Kaggle credentials work. The `kaggle` CLI reads `~/.kaggle/kaggle.json` (or `KAGGLE_USERNAME` / `KAGGLE_KEY`).

**1. Check that the CLI sees your config**

```bash
kaggle config view
```

You should see your **username** and **path** to the config file. If you see "Could not find kaggle.json" or similar, put `kaggle.json` in `~/.kaggle/` and run `chmod 600 ~/.kaggle/kaggle.json`.

**2. Call the API (real handshake)**

```bash
kaggle datasets list --max-size 1
```

This lists one dataset from Kaggle. If it returns a short table and no error, the handshake worked. If you get "403 Forbidden" or "Could not find credentials", fix the config (file or env vars) and try again.

**Success** = `kaggle config view` shows your username and `kaggle datasets list --max-size 1` returns without error.

---

## Step 1: Establish GCP connection (one-time per machine)

These use your Google account and create a credentials file Terraform (and the app) will use. **No API key**—connection is via login + Application Default Credentials.

```bash
# 1. Log in (opens browser)
gcloud auth login

# 2. Set the project Terraform will use (must match terraform.tfvars project_id)
gcloud config set project horizon-platform-488122

# 3. Create credentials file for Terraform and Python (opens browser again)
gcloud auth application-default login
```

**Why:** Terraform talks to GCP over HTTPS using the credentials from step 3. Without step 3, `terraform plan` / `apply` will fail with permission errors.

---

## Step 2: Enable required APIs (one-time per project)

Terraform creates GCS, BigQuery, Pub/Sub, and IAM resources. Their APIs must be enabled:

```bash
export PROJECT_ID=horizon-platform-488122

gcloud services enable storage.googleapis.com bigquery.googleapis.com pubsub.googleapis.com iam.googleapis.com --project=$PROJECT_ID
```

---

## Step 3: Run Terraform

From the **terraform** directory:

```bash
cd terraform

# Download provider and init state
terraform init

# See what will be created (no changes yet)
terraform plan

# Create resources (type 'yes' when prompted, or use -auto-approve)
terraform apply
```

To apply without prompt:

```bash
terraform apply -auto-approve
```

---

## Step 4: Export outputs for the app

After a successful apply:

```bash
export GCS_BUCKET=$(terraform output -raw gcs_bucket_name)
export GOOGLE_CLOUD_PROJECT=$(terraform output -raw project_id)
export BIGQUERY_DATASET=$(terraform output -raw bigquery_dataset_id)
```

Use these when running `run_ingestion.py` and `scripts/load_gcs_to_bigquery.py`.

---

## Step 5: What to run after Terraform and GCP are complete

Once Terraform has been applied and you have exported the outputs (Step 4), run the pipeline in this order.

**1. Export outputs (if not already in this shell)**

From project root:

```bash
cd terraform
export GCS_BUCKET=$(terraform output -raw gcs_bucket_name)
export GOOGLE_CLOUD_PROJECT=$(terraform output -raw project_id)
export BIGQUERY_DATASET=$(terraform output -raw bigquery_dataset_id)
cd ..
```

**2. Ingest from sources to GCS (Parquet)**

Pulls data from Kaggle (and/or Hugging Face), normalizes it, and writes Parquet to your GCS bucket. For Kaggle you need `~/.kaggle/kaggle.json` or `KAGGLE_USERNAME` + `KAGGLE_KEY` set.

```bash
# One source (recommended first time)
python run_ingestion.py --source kaggle_data_engineer

# Or all sources
python run_ingestion.py --source all
```

**3. Load GCS Parquet into BigQuery**

Creates or replaces the raw tables in the `job_market_analysis` dataset.

```bash
python scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer
# Or: --source all
```

**4. Optional: create the master view**

Single view over all raw tables:

```bash
python scripts/create_master_table.py
```

**5. Optional: compare skills extraction (taxonomy vs LLM)**

Uses a sample from CSV or BigQuery; needs `GOOGLE_API_KEY` if you don’t use `--skip-llm`:

```bash
python scripts/compare_skills_extraction.py --from-bigquery --sample 100 --output comparison_skills.csv --print-metrics
```

**Summary order:** Terraform + GCP done → export outputs → **run_ingestion.py** → **load_gcs_to_bigquery.py** → (optional) create_master_table.py, compare_skills_extraction.py.

---

## Quick reference

| Step | Command / action |
|------|------------------|
| Log in | `gcloud auth login` |
| Set project | `gcloud config set project YOUR_PROJECT_ID` |
| ADC (for Terraform/app) | `gcloud auth application-default login` |
| Enable APIs | `gcloud services enable storage.googleapis.com bigquery.googleapis.com pubsub.googleapis.com iam.googleapis.com --project=YOUR_PROJECT_ID` |
| Terraform init | `cd terraform && terraform init` |
| Terraform plan | `terraform plan` |
| Terraform apply | `terraform apply` or `terraform apply -auto-approve` |

If you see **403** or **Permission denied**: run Step 1 again (especially `gcloud auth application-default login`).
