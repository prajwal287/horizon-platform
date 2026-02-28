# Horizon Codebase Explained (Like You're 15)

This guide explains **what this project does**, **how it connects to Google Cloud**, **where secrets live on your computer**, and **how Docker runs it**—with simple examples and flowcharts.

---

## 1. What Does This Project Do? (The Big Picture)

Imagine you're building a **job board** that only shows **data-related jobs** (Data Engineer, Data Scientist, etc.). This project:

1. **Fetches** job postings from two places: **Hugging Face** (a free dataset) and **Kaggle** (datasets that need an API key).
2. **Cleans** them: keeps only jobs from the last 3 years and only "data" jobs (filters out non-data roles).
3. **Saves** them to **Google Cloud Storage (GCS)** as Parquet files, so later you can analyze them in BigQuery or other tools.

So in one sentence: **"Get job data from Hugging Face + Kaggle → filter → upload to Google Cloud."**

---

## 2. High-Level Flowchart (The Whole Journey)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         HORIZON – DATA FLOW (SIMPLIFIED)                          │
└─────────────────────────────────────────────────────────────────────────────────┘

  YOU (on your laptop)                    EXTERNAL SERVICES                 GCP (Google Cloud)
  ───────────────────                    ─────────────────                 ─────────────────

        ┌──────────────┐
        │  .env file   │  (your project ID, bucket name, Kaggle username/key)
        │  (secrets)   │
        └──────┬───────┘
               │
        ┌──────▼───────┐     "Run ingestion"
        │ Docker       │
        │ container   │
        └──────┬───────┘
               │
     ┌─────────┼─────────┐
     │         │         │
     ▼         ▼         ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│Hugging  │ │ Kaggle  │ │ GCP     │
│Face API │ │ API     │ │ creds   │
│(public) │ │(need    │ │(from    │
│         │ │ key)    │ │ ~/.config│
└────┬────┘ └────┬────┘ │ /gcloud)│
     │           │      └────┬────┘
     │           │           │
     └───────────┼───────────┘
                 │
        ┌────────▼────────┐
        │  dlt pipeline  │  (reads data → filters → writes Parquet)
        │  (inside       │
        │   container)   │
        └────────┬───────┘
                 │
                 │  Upload (using GCP credentials)
                 ▼
        ┌────────────────────┐
        │  Google Cloud       │
        │  Storage (GCS)     │  ← Parquet files land here
        │  gs://bucket/raw/  │
        └────────────────────┘
```

---

## 3. Step-by-Step: What Happens When You Run a Pipeline?

### Step 1: You run a command

Example:

```bash
docker compose run --rm app python run_ingestion.py --source kaggle_data_engineer
```

- **docker compose run** = start a container from the image defined in `docker-compose.yml`.
- **--rm** = delete the container when it finishes (cleanup).
- **app** = the service name in `docker-compose.yml`.
- **python run_ingestion.py --source kaggle_data_engineer** = the command that runs inside the container.

So you're saying: *"Start the app container, run this Python script for the Kaggle Data Engineer source, then remove the container."*

---

### Step 2: `run_ingestion.py` (the front door)

- It checks that **GCS_BUCKET** is set (from `.env` or environment). If not, it exits with an error.
- It looks at **--source**:
  - `all` → run all 4 pipelines (huggingface, kaggle_data_engineer, kaggle_linkedin, kaggle_linkedin_skills).
  - Or one name → run only that pipeline.
- For each pipeline it calls a function, e.g. `run_kaggle_data_engineer()` which lives in `ingestion/pipelines/run_kaggle_data_engineer.py`.

**Flowchart – run_ingestion.py:**

```
  Start
    │
    ▼
  Parse --source (all / huggingface / kaggle_data_engineer / …)
    │
    ▼
  Is GCS_BUCKET set? ──No──► Error, exit
    │
   Yes
    │
    ▼
  For each chosen source:
    │
    ├─► run_huggingface()
    ├─► run_kaggle_data_engineer()
    ├─► run_kaggle_linkedin()
    └─► run_kaggle_linkedin_skills()
    │
    ▼
  End
```

---

### Step 3: One pipeline (e.g. Kaggle Data Engineer)

Each pipeline uses the shared runner in `ingestion/pipelines/common.py`:

1. **Get GCS bucket URL** from config (which reads `GCS_BUCKET` and `GCS_PREFIX` from the environment).
2. **Set dlt destination**: tell dlt to write to the **filesystem**; that "filesystem" is actually **GCS** (because the path is `gs://bucket/raw/...`).
3. **Create a dlt pipeline** with:
   - a **resource**: a Python generator that yields rows (dicts), using the canonical **JOBS_COLUMNS** from `ingestion/schema.py`.
   - **destination**: `filesystem` (GCS).
   - **write_disposition**: replace (overwrite table each run).
   - **loader_file_format**: parquet.
4. **Run the pipeline**: dlt pulls rows from the resource and writes Parquet to GCS.

**Flowchart – single pipeline (e.g. run_kaggle_data_engineer):**

```
  run()
    │
    ▼
  run_pipeline() in common.py
    │
    ▼
  get_gcs_base_url()  ──►  gs://YOUR_BUCKET/raw
    │
    ▼
  Set DESTINATION__FILESYSTEM__BUCKET_URL = gs://.../raw/kaggle_data_engineer_2023
    │
    ▼
  dlt.pipeline(destination="filesystem", dataset_name=...)
    │
    ▼
  pipeline.run(jobs_resource(), write_disposition="replace", ...)
    │
    ├──────────────────────────────────────┐
    │  jobs_resource()                      │
    │    │                                  │
    │    ▼                                  │
    │  stream_kaggle_data_engineer_2023()   │  ← Source: download CSV from Kaggle,
    │    │                                  │     read in chunks, filter, yield batches
    │    ▼                                  │
    │  yield row, row, row …                │
    └──────────────────────────────────────┘
    │
    ▼
  dlt writes each batch as Parquet to GCS (using GCP credentials)
    │
    ▼
  return pipeline
```

---

## 4. Where does the data come from? (Sources)

- **Hugging Face** (`stream_huggingface_data_jobs`): loads the public dataset `lukebarousse/data_jobs` with the `datasets` library. No API key needed.
- **Kaggle** (e.g. `stream_kaggle_data_engineer_2023`):
  - Calls `download_dataset("lukkardata/data-engineer-job-postings-2023")` in `kaggle_download.py`.
  - That uses **KAGGLE_USERNAME** and **KAGGLE_KEY** (or **KAGGLE_API_TOKEN**) from the **environment** (which Docker got from your `.env`).
  - Downloads the dataset to a folder (inside the container it's under `/app/data/kaggle/...` because of the volume mount).
  - Then the source reads the CSV in chunks, normalizes columns, filters (last 3 years, data-domain only), and yields rows in the **RawJobRow** schema.

So:

- **Hugging Face**: data comes from the internet (API) when the pipeline runs.
- **Kaggle**: dataset is **downloaded to the container's filesystem** (under `/app/data`), then read from there. The "files" are on the container; if you mount `./data` in Docker, they appear under `./data/kaggle/...` on your **host** too.

---

## 5. Where do the rows go? (GCS)

- **Config** (`ingestion/config.py`): reads **GCS_BUCKET** and **GCS_PREFIX** from the environment; `get_gcs_base_url()` returns `gs://BUCKET/PREFIX`.
- **Pipelines** (via `common.run_pipeline`) set **DESTINATION__FILESYSTEM__BUCKET_URL** to something like `gs://BUCKET/raw/huggingface_data_jobs` or `gs://BUCKET/raw/kaggle_data_engineer_2023`.
- **dlt** with `destination="filesystem"` and the `gs://` URL uses the **GCP credentials** (see below) to write Parquet files into that path in GCS.

So: **connection to GCP** for writing is done by **dlt + the GCP credentials**; the "connection" is just: "use the credentials and write to this `gs://` path."

---

## 6. How Is the Connection to GCP Made?

There is **no** custom "connect to GCP" code in this repo. Connection is done by:

1. **Google client libraries** (used by dlt under the hood) that look for **Application Default Credentials (ADC)**.
2. **ADC** is set via the environment variable **GOOGLE_APPLICATION_CREDENTIALS** = path to a JSON key file.
3. In **Docker**, that path is set to **`/app/gcloud/application_default_credentials.json`**.
4. That file **does not** live in the repo. It lives on your **host** at:

   **`~/.config/gcloud/application_default_credentials.json`**

5. **Docker Compose** mounts your host folder into the container:

   ```yaml
   volumes:
     - ${HOME}/.config/gcloud:/app/gcloud:ro
   ```

   So inside the container, `/app/gcloud/application_default_credentials.json` is the same file as `~/.config/gcloud/application_default_credentials.json` on your Mac/Linux. **Read-only (`ro`)** so the container cannot change it.

You create that file by running **once** on your host:

```bash
gcloud auth application-default login
```

So:

- **Where** connection is "made": inside **dlt** and Google's libraries, when they read **GOOGLE_APPLICATION_CREDENTIALS** and load that JSON.
- **How** it's set up: **Docker mounts your local gcloud config** into the container and sets **GOOGLE_APPLICATION_CREDENTIALS** to point at the mounted file.

---

## 7. Where Are Files and Secrets Stored Locally?

### 7.1 GCP credentials (for GCS/BigQuery etc.)

| What              | Where on your computer                                      | Used in Docker as                                              |
|-------------------|-------------------------------------------------------------|----------------------------------------------------------------|
| ADC (login file)  | `~/.config/gcloud/application_default_credentials.json`      | Mounted at `/app/gcloud/` and `GOOGLE_APPLICATION_CREDENTIALS=/app/gcloud/application_default_credentials.json` |

- **Not** in the repo.
- You create it with: `gcloud auth application-default login`.

### 7.2 Project ID and GCS bucket name

- Stored in **`.env`** in the **project root** (same folder as `docker-compose.yml`):
  - **GOOGLE_CLOUD_PROJECT** = your GCP project ID.
  - **GCS_BUCKET** = bucket name (e.g. from Terraform: `terraform -chdir=terraform output -raw gcs_bucket_name`).

Docker Compose loads `.env` and passes these into the container as environment variables. So **keys** for "which project and which bucket" are in **`.env`** on your machine; the container sees them as env vars.

### 7.3 Kaggle API credentials

- Also in **`.env`**:
  - **KAGGLE_USERNAME**
  - **KAGGLE_KEY** (or **KAGGLE_API_TOKEN**)

Same idea: **`.env`** on the host → env vars in the container. The Kaggle library inside the container reads `KAGGLE_USERNAME` and `KAGGLE_KEY` from the environment.

You can also put `kaggle.json` (downloaded from Kaggle) in **`./secrets`**; Docker mounts **`./secrets`** at **`/app/secrets`**. The code in this repo uses **env vars**, not the file, but having `kaggle.json` in `./secrets` is a common pattern if you ever want to point the Kaggle client at a file.

Summary:

| Secret / config   | Where it lives locally                                      | How the container gets it                          |
|-------------------|-------------------------------------------------------------|----------------------------------------------------|
| GCP ADC           | `~/.config/gcloud/application_default_credentials.json`     | Volume mount `~/.config/gcloud` → `/app/gcloud`    |
| Project ID, bucket| `.env` (GOOGLE_CLOUD_PROJECT, GCS_BUCKET)                   | `env_file: .env` + `environment` in docker-compose |
| Kaggle            | `.env` (KAGGLE_USERNAME, KAGGLE_KEY) or `./secrets`         | `env_file` + `environment` (and optional mount)    |

---

## 8. How Is Docker Set Up to Run Locally?

### 8.1 Dockerfile (build stage)

- **Base image**: `python:3.10-slim`.
- **Working directory**: `/app`.
- **Install**: `pip install -r requirements.txt` (dlt, pandas, kaggle, etc.).
- **Copy**: `ingestion/`, `run_ingestion.py`, and `scripts/` into `/app`.
- **Default command**: `tail -f /dev/null` (keep the container running so you can run one-off commands like `python run_ingestion.py ...`).

So the image is: Python + dependencies + your code. No secrets inside the image.

### 8.2 docker-compose.yml (run stage)

- **Service name**: `app`.
- **Build**: current directory (`.`), so it uses the Dockerfile above.
- **Volumes** (mounts from host into container):
  - `./data` → `/app/data` (Kaggle downloads and any local data).
  - `./secrets` → `/app/secrets` (optional; for files like `kaggle.json`).
  - `${HOME}/.config/gcloud` → `/app/gcloud:ro` (GCP credentials; read-only).
- **Env**:
  - **env_file: .env** (optional): load variables from `.env`.
  - **environment**: sets **GOOGLE_APPLICATION_CREDENTIALS**, **GOOGLE_CLOUD_PROJECT**, **GCS_BUCKET**, **KAGGLE_USERNAME**, **KAGGLE_KEY**, **KAGGLE_API_TOKEN** (from `.env` or host env).

So when you run:

```bash
docker compose run --rm app python run_ingestion.py --source kaggle_data_engineer
```

Docker:

1. Builds the image (if needed).
2. Creates a container with:
   - your code at `/app`,
   - `.env` and env vars for project, bucket, Kaggle,
   - GCP credentials from `~/.config/gcloud` mounted at `/app/gcloud`,
   - `./data` and `./secrets` mounted.
3. Runs `python run_ingestion.py --source kaggle_data_engineer` inside that container.
4. Removes the container when the command exits (`--rm`).

**Flowchart – Docker setup:**

```
  YOUR MACHINE (host)                    CONTAINER (app)
  ───────────────────                    ───────────────

  Project root/
  ├── .env                    ──env_file──►  GOOGLE_CLOUD_PROJECT, GCS_BUCKET,
  ├── docker-compose.yml                   KAGGLE_USERNAME, KAGGLE_KEY, ...
  ├── Dockerfile
  ├── run_ingestion.py        ──copy in──►  /app/run_ingestion.py
  ├── ingestion/             ──copy in──►  /app/ingestion/
  ├── data/                  ──mount────►  /app/data/
  └── secrets/               ──mount────►  /app/secrets/

  ~/.config/gcloud/          ──mount────►  /app/gcloud/   (ro)
  └── application_default_credentials.json
```

---

## 9. Terraform's Role (GCP Resources)

Terraform **does not** run inside Docker. You run it on your **host** (after `terraform init` and with `terraform.tfvars` set).

It creates in GCP:

- A **GCS bucket** (e.g. `YOUR_PROJECT_ID-job-lakehouse-raw`) for raw data.
- A **BigQuery dataset** (e.g. `job_market_analysis`).
- A **Pub/Sub topic** (e.g. for future real-time ingestion).
- A **service account** and IAM bindings.

The **ingestion containers** do **not** use that service account key. They use **your** ADC (`gcloud auth application-default login`). So:

- **Terraform** = create bucket, dataset, etc., in GCP.
- **Your laptop + Docker** = use your user credentials (ADC) to write into that bucket.

Later you could switch to using the Terraform-created service account (e.g. key file or Workload Identity); for now, ADC is the "connection" from your local Docker to GCS.

---

## 10. Quick Reference: Commands and What They Do

| What you want                 | Command / step |
|-------------------------------|----------------|
| Create GCP resources          | `cd terraform` → `terraform init` → `terraform apply` |
| Get bucket name / project ID  | `terraform -chdir=terraform output -raw gcs_bucket_name` and `project_id` |
| One-time GCP login (ADC)      | `gcloud auth application-default login` |
| Put project + bucket + Kaggle| Copy `.env.example` to `.env` and fill in values |
| Build Docker image            | `docker compose build` |
| Run all pipelines             | `docker compose run --rm app python run_ingestion.py --source all` |
| Run one pipeline              | `docker compose run --rm app python run_ingestion.py --source kaggle_data_engineer` |

---

## 11. One-Page "Flow" Summary

1. **You**: run `docker compose run --rm app python run_ingestion.py --source kaggle_data_engineer`.
2. **Docker**: starts container with code at `/app`, env from `.env`, GCP creds from `~/.config/gcloud` at `/app/gcloud`.
3. **run_ingestion.py**: checks `GCS_BUCKET`, then calls `run_kaggle_data_engineer()`.
4. **Pipeline** (in `common.run_pipeline`): sets dlt destination to `gs://BUCKET/raw/kaggle_data_engineer_2023`, creates a pipeline with a resource that yields rows (using `JOBS_COLUMNS` from schema).
5. **Resource**: calls `stream_kaggle_data_engineer_2023()` → Kaggle download (using `KAGGLE_*` from env) to `/app/data/kaggle/...`, reads CSV, filters, yields batches of dicts.
6. **dlt**: writes each batch as Parquet to GCS using ADC at `GOOGLE_APPLICATION_CREDENTIALS`.
7. **Container** exits; you get Parquet files in GCS under `gs://BUCKET/raw/kaggle_data_engineer_2023/`.

That's the full path from your command to data in GCP, with credentials and files coming from your local `.env`, `~/.config/gcloud`, and optional `./data` and `./secrets` mounts.

---

## 12. Mermaid flowcharts

For diagrams that render in GitHub or VS Code (with a Mermaid extension), see [CODEBASE_FLOWCHARTS.md](CODEBASE_FLOWCHARTS.md) in this folder. It has:

- End-to-end flow (your laptop → Docker → Hugging Face/Kaggle → GCS)
- run_ingestion.py decision flow
- Single pipeline flow (e.g. Kaggle Data Engineer)
- Where secrets live (local → container)
- Docker build and run
