# Run from Scratch: Terraform, GCP, and DLT

This guide walks you through running the project from zero. It explains **each component**, **how connections are established**, **what gets created**, and **how the pieces connect**. No jargon dumps—one idea at a time.

---

# Part 1: Terraform and GCP

## What you’re doing in one sentence

You will use **Terraform** to create the **GCP resources** (a bucket, a BigQuery dataset, a Pub/Sub topic, and a service account with permissions) that the ingestion and load scripts need. Then you’ll see how **your machine talks to GCP** and how **no API key is used for GCP**—only login and a credentials file.

---

## 1.1 What is Terraform here?

- **Terraform** = a tool that reads **code files** (`.tf`) that describe “I want this bucket, this dataset, this service account,” and then **creates those things in GCP** when you run `terraform apply`.
- So: **infrastructure as code**. The files in `terraform/` are the single source of truth for *what* exists in GCP.

You don’t create the bucket or dataset by clicking in the Console; Terraform does it from the code.

---

## 1.2 How does Terraform connect to GCP? (Security / “how the call is made”)

Terraform does **not** use an API key for GCP. It uses **your Google identity** and a **credentials file** on your machine.

1. You run **`gcloud auth login`**  
   - A browser opens; you sign in with your Google account.  
   - This logs **you** into the Cloud SDK (gcloud).

2. You run **`gcloud auth application-default login`**  
   - You sign in again in the browser (same or different account).  
   - This writes a **credentials file** to a standard location on your machine (e.g. `~/.config/gcloud/application_default_credentials.json`).

3. When you run **`terraform plan`** or **`terraform apply`**:
   - Terraform uses the **Google provider** (a plugin that knows how to create GCS buckets, BigQuery datasets, etc.).
   - The provider reads **Application Default Credentials (ADC)** from that file.
   - Every call Terraform makes to GCP (create bucket, create dataset, set IAM, etc.) is an **HTTPS request** to GCP APIs, with those credentials attached.
   - So: **connection = your machine → HTTPS → GCP APIs**, authenticated by the credentials file. No API key in the code or in Terraform.

4. You also run **`gcloud config set project YOUR_PROJECT_ID`**  
   - So gcloud (and Terraform via the provider) know **which GCP project** to use. The Terraform variable `project_id` should match this.

**Summary:** GCP connection = **gcloud login** + **application-default login** → credentials file → Terraform (and later, the Python app) use that same file to talk to GCP. No GCP API key anywhere.

---

## 1.3 What gets created (components)

When you run `terraform apply`, Terraform creates these **resources** in your GCP project:

| # | Resource in code | What it is in GCP |
|---|-------------------|--------------------|
| 1 | **GCS bucket** | A bucket to store raw data (Parquet files). Name = `{project_id}-{gcs_bucket_name}` (e.g. `my-project-job-lakehouse-raw`). Has a lifecycle rule: after 90 days, objects move to Nearline storage (cheaper). |
| 2 | **BigQuery dataset** | A dataset (e.g. `job_market_analysis`) where tables like `raw_kaggle_data_engineer_2023` will live. This is where you run SQL for analytics. |
| 3 | **Pub/Sub topic** | A topic (e.g. `job-stream-input`) for real-time ingestion. The project uses it for future streaming; the current ingestion is batch (Kaggle/Hugging Face → GCS → BigQuery). |
| 4 | **Service account** | An identity (e.g. `lakehouse-sa@your-project.iam.gserviceaccount.com`) that can be used by pipelines or jobs to access GCS/BigQuery/Pub/Sub without using your personal login. |
| 5–7 | **IAM bindings** | Permissions for that service account: (5) Storage Object Admin on the bucket, (6) BigQuery Admin on the project, (7) Pub/Sub Publisher on the topic. |

So after `apply`: you have one bucket, one dataset, one topic, one service account, and three permission bindings. The **Python ingestion and load scripts** use the **same** Application Default Credentials (your `gcloud auth application-default login`), so they can read/write that bucket and load data into that dataset. The service account is there for when you run jobs as that identity (e.g. in Cloud Run or a VM).

---

## 1.4 Variables: what they are and where they’re set

**Variables** are inputs to the Terraform config. They let you change project, region, or names without editing the core logic.

- **Defined in:** `terraform/variables.tf`  
  Each variable has a **name**, a **description**, a **type**, and optionally a **default** value.

- **Set in (optional):** `terraform/terraform.tfvars`  
  You can copy `terraform.tfvars.example` to `terraform.tfvars` and put your `project_id` (and optionally `region`, etc.) there. If you don’t set a variable in `terraform.tfvars`, Terraform uses the **default** from `variables.tf`.

Main variables:

| Variable | Purpose | Default (in variables.tf) |
|----------|---------|----------------------------|
| `project_id` | GCP project where resources are created | e.g. `horizon-platform-488122` |
| `project_name` | Display name used in labels | e.g. `Horizon-platform` |
| `region` | Region for bucket and dataset | `us-central1` |
| `gcs_bucket_name` | Suffix for bucket name (full name = `{project_id}-{gcs_bucket_name}`) | `job-lakehouse-raw` |
| `bigquery_dataset_id` | BigQuery dataset name | `job_market_analysis` |
| `pubsub_topic_name` | Pub/Sub topic name | `job-stream-input` |
| `service_account_name` | Short name for the service account | `lakehouse-sa` |
| `lifecycle_nearline_days` | After how many days GCS objects move to Nearline | `90` |

So: **variables** = knobs you can turn; **terraform.tfvars** = where you set them for your run (or rely on defaults).

---

## 1.5 Outputs: what Terraform gives you after apply

**Outputs** are values Terraform prints after `apply` (and when you run `terraform output`). They’re the “answers” you need to run the rest of the project.

- **Defined in:** `terraform/outputs.tf`  
  Each output has a **name** and a **value** (e.g. the bucket name, the dataset id, the service account email).

Main outputs:

| Output | What it is |
|--------|------------|
| `project_id` | Your GCP project ID |
| `gcs_bucket_name` | Full bucket name (e.g. `my-project-job-lakehouse-raw`) |
| `gcs_bucket_uri` | Full URI (e.g. `gs://my-project-job-lakehouse-raw`) |
| `bigquery_dataset_id` | Dataset name (e.g. `job_market_analysis`) |
| `bigquery_dataset_full_id` | Full dataset ID (project.dataset) |
| `pubsub_topic_name` | Topic name |
| `service_account_email` | Service account email (e.g. for IAM or pipelines) |

**How the app uses them:**  
Your ingestion and load scripts don’t read Terraform state. **You** set **environment variables** from these outputs, for example:

- `GCS_BUCKET` = value of `gcs_bucket_name` (or the bucket name without `gs://`)
- `GOOGLE_CLOUD_PROJECT` = `project_id`
- `BIGQUERY_DATASET` = `bigquery_dataset_id`

So: **Terraform outputs** → you copy into env vars (or a `.env` file) → the Python code reads those env vars and uses them to know where to write Parquet and which BigQuery dataset to use.

---

## 1.6 Step-by-step: run Terraform from scratch

Do this from your **project root** (parent of `terraform/`).

**Step 0: Prerequisites**

- Install **gcloud** and **Terraform** (see `terraform/README.md`).
- Have a **GCP project** (create one in the Console if needed) and note the **Project ID**.

**Step 1: Log in and set project**

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login
```

- **Why:** So Terraform (and later the Python app) can call GCP APIs using your identity. No API key; the “connection” is this credentials file.

**Step 2: Enable APIs**

```bash
export PROJECT_ID=YOUR_PROJECT_ID
gcloud services enable storage.googleapis.com bigquery.googleapis.com pubsub.googleapis.com iam.googleapis.com --project=$PROJECT_ID
```

- **Why:** Terraform creates resources by calling these APIs. If they’re not enabled, the calls fail.

**Step 3: Set Terraform variables**

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars and set project_id (and optionally region, etc.) to your values.
```

**Step 4: Initialize Terraform**

```bash
terraform init
```

- **What it does:** Downloads the Google provider (the plugin that knows how to create buckets, datasets, etc.) into `.terraform/`. Run once per Terraform directory (and again if you add a new provider).

**Step 5: Plan (preview)**

```bash
terraform plan
```

- **What it does:** Compares your `.tf` files to the current state (empty on first run) and prints what would be created. **No resources are created yet.**

**Step 6: Apply (create resources)**

```bash
terraform apply
```

- When prompted, type **yes**. Terraform will create the bucket, dataset, topic, service account, and IAM bindings. At the end it prints the **outputs**.

**Step 7: Export outputs for the app**

```bash
export GCS_BUCKET=$(terraform output -raw gcs_bucket_name)
export GOOGLE_CLOUD_PROJECT=$(terraform output -raw project_id)
export BIGQUERY_DATASET=$(terraform output -raw bigquery_dataset_id)
```

- **Why:** So when you run `run_ingestion.py` and `load_gcs_to_bigquery.py`, they know which bucket and dataset to use. They read these env vars (and use the same GCP credentials from Step 1).

You’re done with Part 1. The “connection” to GCP is: **ADC from `gcloud auth application-default login`**; variables tell Terraform *what* to create; outputs tell *you* what to put in env vars for the app.

---

## 1.7 Kaggle: how that connection works (separate from GCP)

Kaggle is **not** created or configured by Terraform. The **Python ingestion code** downloads datasets using the **Kaggle API**.

- **Auth:** Kaggle expects either:
  - A file **`~/.kaggle/kaggle.json`** with `username` and `key`, or  
  - Environment variables **`KAGGLE_USERNAME`** and **`KAGGLE_KEY`** (some docs say `KAGGLE_API_TOKEN`; the library often accepts `KAGGLE_KEY`).
- **What happens:** When you run ingestion for a Kaggle source (e.g. `run_ingestion.py --source kaggle_data_engineer`), the code calls Kaggle’s API to download the dataset (e.g. to `data/kaggle/...`). That’s an **HTTPS request to Kaggle** with your Kaggle credentials—no GCP involved in that step.
- **Summary:** GCP = your credentials (ADC). Kaggle = your Kaggle username + key (file or env). Two separate connections.

---

# Part 2: DLT – How it works and how we use it

## 2.1 What is DLT in one sentence?

**dlt** (data load tool) is a **Python library** that takes data you produce in Python (e.g. rows from a generator) and **loads** it into a **destination** (e.g. files on a “filesystem,” which in our case is **GCS**). It handles batching, file format (e.g. Parquet), and write mode (e.g. replace).

So: **your code yields rows → dlt writes them to the destination.** You don’t write the “write to GCS” logic yourself; dlt does it.

---

## 2.2 How we use DLT in this project

All pipelines (Hugging Face, Kaggle Data Engineer, etc.) go through **one shared function** in `ingestion/pipelines/common.py`: **`run_pipeline`**.

- **Inputs:** A pipeline name, a dataset name (used in the path), and a **stream function** that yields **batches of dicts** (each dict = one job row).
- **What it does:**
  1. Builds the **GCS path** for that dataset: `gs://{bucket}/raw/{dataset_name}`.
  2. Sets **`DESTINATION__FILESYSTEM__BUCKET_URL`** to that path. (dlt reads this env var when the destination is `filesystem` and the URL is `gs://...`.)
  3. Defines a **dlt resource**: a generator that, when run, calls your stream function and yields one dict per job row.
  4. Creates a **dlt pipeline** with `destination="filesystem"` and `dataset_name=...`.
  5. Runs the pipeline with that resource and **loader_file_format="parquet"**.

So: **stream function** (e.g. `stream_kaggle_data_engineer_2023`) → **batches of dicts** → **resource** yields one dict per row → **dlt** writes Parquet under the given GCS path. The **columns** (schema) come from **`JOBS_COLUMNS`** in `ingestion/schema.py` so every pipeline writes the same shape.

---

## 2.3 How does DLT connect to GCS?

- dlt’s **filesystem** destination can write to **local disk** or to **GCS** when the path is a **`gs://...`** URL.
- When the URL is `gs://bucket/...`, dlt uses **Google Cloud storage libraries** under the hood. Those libraries use the **same Application Default Credentials** as Terraform and the rest of your app.
- So: **no extra config for GCS auth**—as long as you’ve run `gcloud auth application-default login` and set `GCS_BUCKET` (and thus the bucket URL) correctly, dlt can write to GCS. The “connection” is again **ADC**.

---

## 2.4 Flow in code (one pipeline example)

1. You run: **`python run_ingestion.py --source kaggle_data_engineer`**  
   - `run_ingestion.py` checks env (`GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT`), then calls **`run_kaggle_data_engineer()`**.

2. **`run_kaggle_data_engineer()`** (in `ingestion/pipelines/run_kaggle_data_engineer.py`) calls:
   - **`run_pipeline(PIPELINE_NAME, DATASET_NAME, stream_kaggle_data_engineer_2023)`**.

3. **`run_pipeline`** (in `common.py`):
   - Gets **bucket base** from **`get_gcs_base_url()`** (uses `GCS_BUCKET` from config).
   - Sets **`DESTINATION__FILESYSTEM__BUCKET_URL`** = `gs://{bucket}/raw/kaggle_data_engineer_2023`.
   - Defines **`jobs_resource()`**: for each batch from **`stream_kaggle_data_engineer_2023()`**, yields each row dict. The resource is decorated with **`@dlt.resource(name="jobs", write_disposition="replace", columns=JOBS_COLUMNS)`**.
   - Creates **`dlt.pipeline(pipeline_name=..., destination="filesystem", dataset_name=...)`**.
   - Runs **`pipeline.run(jobs_resource(), loader_file_format="parquet")`**.

4. **`stream_kaggle_data_engineer_2023()`** (in `ingestion/sources/kaggle_data_engineer_2023.py`):
   - Downloads the Kaggle dataset (using Kaggle credentials) if needed.
   - Reads the CSV in chunks, maps columns to the canonical schema, builds **`RawJobRow`** instances, converts to dicts with **`to_load_dict()`**, and yields batches of those dicts.

5. **dlt** consumes the stream of dicts, batches them, and writes **Parquet** files under **`gs://{bucket}/raw/kaggle_data_engineer_2023/`**. So the “underlying logic” is: **Python generator → dlt → Parquet in GCS.**

---

## 2.5 Concepts to remember (80/20)

| Concept | Meaning |
|--------|---------|
| **Resource** | A Python generator (yielding dicts) + `@dlt.resource(...)`. dlt pulls from it and writes to the destination. |
| **Pipeline** | A runnable unit: one (or more) resources + a destination. We use one resource per pipeline. |
| **Destination** | Where data lands. We use **filesystem** with a **GCS URL**, so “filesystem” = GCS. |
| **write_disposition="replace"** | Each run replaces the data at the destination (no appends). So re-running gives the same number of rows, not duplicates. |
| **JOBS_COLUMNS** | Schema for the `jobs` table; same for all pipelines so every source writes the same columns. |

---

## What to do next

- Run **Part 1** (Terraform + GCP) and then set **`GCS_BUCKET`**, **`GOOGLE_CLOUD_PROJECT`**, **`BIGQUERY_DATASET`** from the outputs.
- Run **ingestion** for one source (e.g. Kaggle Data Engineer). Set **Kaggle** credentials (env or `~/.kaggle/kaggle.json`) so the download works.
- Then run **`scripts/load_gcs_to_bigquery.py`** for that source and query the table in BigQuery.

If you want, we can go deeper next on **one** of: (a) a single Terraform resource (e.g. the bucket) line by line, (b) the exact flow in `common.py` and `stream_kaggle_data_engineer_2023`, or (c) how to run and verify one pipeline end-to-end on your machine.
