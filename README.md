# Horizon

The Data Architecture & Agentic AI Intelligence Platform — data-domain job postings ingestion (Hugging Face + Kaggle) into GCS via dlt.

## Running ingestion

1. **Rebuild the image** (so the container has `run_ingestion.py` and `ingestion/`):
   ```bash
   docker compose build
   ```
   Run from the project root (where `docker-compose.yml` and `Dockerfile` live).

2. **GCP credentials and project** (required for writing to GCS):
   - **Application Default Credentials** — On your host, run:
     ```bash
     gcloud auth application-default login
     ```
     This creates `~/.config/gcloud/application_default_credentials.json`. Docker Compose mounts that folder into the container so GCS is not "anonymous".
   - **Project ID** — Set so the container knows which GCP project to use:
     ```bash
     export GOOGLE_CLOUD_PROJECT=$(terraform -chdir=terraform output -raw project_id)
     ```
     Or set `GOOGLE_CLOUD_PROJECT=your-gcp-project-id` in `.env`. Without this you get "No project ID could be determined" and GCS may reject with 401.

3. **Set GCS bucket** (from Terraform):
   ```bash
   export GCS_BUCKET=$(terraform -chdir=terraform output -raw gcs_bucket_name)
   ```
   Or copy `.env.example` to `.env` and set `GCS_BUCKET=your-project-job-lakehouse-raw`.

4. **Get Kaggle API credentials** (required for Kaggle pipelines like `kaggle_data_engineer`):
   - Go to [kaggle.com](https://www.kaggle.com) and sign in.
   - Profile (top right) → **Settings** → scroll to **API** → **Create New Token**.
   - This downloads `kaggle.json` with `username` and `key`.
   - **Put them in `.env`** so the container gets them (copy `.env.example` to `.env` and fill in):
     ```
     KAGGLE_USERNAME=your_username
     KAGGLE_API_TOKEN=your_key
     ```
   - Or use `KAGGLE_KEY` instead of `KAGGLE_API_TOKEN`. The container loads `.env` automatically when you run `docker compose run`.

5. **Run all pipelines** (Hugging Face + Kaggle → GCS Parquet):
   ```bash
   docker compose run --rm app python run_ingestion.py --source all
   ```
   For Kaggle sources, `KAGGLE_USERNAME` and `KAGGLE_KEY` must be set (e.g. in `.env` or via `environment` in docker-compose).

6. **Run a single source**:
   ```bash
   docker compose run --rm app python run_ingestion.py --source huggingface
   docker compose run --rm app python run_ingestion.py --source kaggle_data_engineer
   ```

## Project layout

- **terraform/** — GCP IaC (GCS, BigQuery, Pub/Sub, service account).
- **ingestion/** — dlt pipelines and sources (Hugging Face `data_jobs`, Kaggle job datasets).
- **run_ingestion.py** — CLI to run one or all pipelines.

See [terraform/README.md](terraform/README.md) for infrastructure setup.
