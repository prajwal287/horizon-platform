# How the Code Works (End-to-End)

One place to understand **what the project does**, **how data flows**, and **which file does what**.

---

## 1. What the project does

- **Fetches** job postings from Hugging Face, Kaggle (several datasets), and optionally Jobven (US, last 24h).
- **Normalizes** them to one shape (same columns for every source).
- **Writes** to GCS as Parquet (Step 1), then **loads** into BigQuery raw tables (Step 2).
- **Optionally** builds a single `master_jobs` view/table (union of all raw tables) for analytics.

So: **Sources → normalize → GCS (Parquet) → BigQuery (raw_*) → optional master_jobs.**

---

## 2. Data flow (two steps)

```
  YOU RUN                          STEP 1                              STEP 2
  ────────                         ──────                              ──────
  run_ingestion.py    →    dlt writes Parquet to GCS    →    load_gcs_to_bigquery.py
  --source X                     (per source)                          loads into BigQuery
                                                                       raw_* tables

  OPTIONAL: create_master_table.py  →  VIEW (or table) "master_jobs" = UNION of all raw_*
```

- **Step 1:** `run_ingestion.py` runs a dlt pipeline per source. Each pipeline reads from the source (API or CSV), turns rows into the canonical schema, and writes Parquet under `gs://<bucket>/raw/<source_slug>/`.
- **Step 2:** `scripts/load_gcs_to_bigquery.py` finds those Parquet files and loads them into BigQuery with WRITE_TRUNCATE (replace). Table names: `raw_huggingface_data_jobs`, `raw_kaggle_data_engineer_2023`, `raw_jobven_jobs`, etc.
- **Master:** `scripts/create_master_table.py` builds a view (or table) that UNIONs all existing raw tables so you can query one place.

---

## 3. How Step 1 works (ingestion)

1. **run_ingestion.py**  
   - Reads `.env` if present.  
   - Checks `GCS_BUCKET` and `GOOGLE_CLOUD_PROJECT`.  
   - Dispatches to the right pipeline (e.g. `run_kaggle_data_engineer()` for `--source kaggle_data_engineer`).

2. **ingestion/pipelines/run_*.py** (e.g. `run_kaggle_data_engineer.py`)  
   - Calls `run_pipeline(pipeline_name, dataset_name, stream_fn)`.  
   - `stream_fn` is the function that yields batches of job rows (e.g. `stream_kaggle_data_engineer_2023`).

3. **ingestion/pipelines/common.py**  
   - `run_pipeline()` sets the dlt destination URL to `gs://<bucket>/raw/<dataset_name>/`.  
   - Defines one dlt resource `jobs` with columns from `ingestion/schema.JOBS_COLUMNS`.  
   - The resource iterates over `stream_fn()` and yields each row.  
   - Runs `pipeline.run(..., loader_file_format="parquet")` so dlt writes Parquet to GCS.

4. **ingestion/sources/*.py** (e.g. `kaggle_data_engineer_2023.py`, `jobven_jobs.py`)  
   - Download or open the source (Kaggle CSV, Hugging Face dataset, or Jobven API).  
   - Read in chunks or pages; for each row map columns to canonical names and build a `RawJobRow`.  
   - Optionally fill `skills` from title/description (taxonomy) if `EXTRACT_SKILLS_TAXONOMY=1` (Kaggle DE).  
   - Yield batches of `RawJobRow.to_load_dict()`.

5. **ingestion/schema.py**  
   - `RawJobRow`: one canonical shape (source_id, job_title, job_description, company_name, location, posted_date, job_url, skills, salary_info, ingested_at).  
   - `to_load_dict()` returns a dict for dlt (dates/timestamps as JSON-serializable).  
   - `JOBS_COLUMNS`: column types for the dlt table.

So: **CLI → pipeline runner → run_pipeline (dlt) → stream_* (source) → RawJobRow → Parquet in GCS.**

---

## 4. How Step 2 works (load to BigQuery)

- **scripts/load_gcs_to_bigquery.py**  
  - For each source (or `--source all`), it knows the GCS prefix (e.g. `raw/kaggle_data_engineer_2023/`, `raw/jobven_jobs/`) and the BigQuery table name (e.g. `raw_kaggle_data_engineer_2023`, `raw_jobven_jobs`).  
  - Uses gcsfs to list Parquet files under that prefix, normalizes URIs to `gs://...`.  
  - Calls BigQuery `load_table_from_uri` with WRITE_TRUNCATE and Parquet format.  
  - So: **GCS Parquet → one raw_* table per source.**

---

## 5. How the master table works

- **scripts/create_master_table.py**  
  - Lists tables in the BigQuery dataset and keeps only the known raw_* tables that exist.  
  - Builds a SQL query: either a simple `SELECT * FROM raw_1 UNION ALL SELECT * FROM raw_2 ...` or a “clean” version with consistent types and an `is_complete` flag.  
  - Creates either a **view** (`CREATE OR REPLACE VIEW master_jobs AS ...`) or a **materialized table** (TRUNCATE + INSERT).  
  - So: **existing raw_* tables → one view/table `master_jobs`.**

---

## 6. Key files (short reference)

| File | Role |
|------|------|
| **run_ingestion.py** | CLI for Step 1; env check; calls pipeline runners. |
| **ingestion/config.py** | GCS_BUCKET, dataset name, skills taxonomy lists. |
| **ingestion/schema.py** | RawJobRow, JOBS_COLUMNS (canonical shape). |
| **ingestion/pipelines/common.py** | run_pipeline(): dlt resource + GCS destination. |
| **ingestion/pipelines/run_*.py** | One per source; calls run_pipeline with the right stream_*. |
| **ingestion/sources/*.py** | Stream rows from Hugging Face / Kaggle / Jobven → RawJobRow batches. |
| **ingestion/skills_extraction.py** | Taxonomy (regex) skills from title/description; used if EXTRACT_SKILLS_TAXONOMY=1. |
| **scripts/load_gcs_to_bigquery.py** | Step 2: GCS Parquet → BigQuery raw_*. |
| **scripts/create_master_table.py** | Union of raw_* → view or table master_jobs. |

---

## 7. Where to run what

- **First time (nothing exists):** [RUN_FROM_SCRATCH.md](RUN_FROM_SCRATCH.md) and [RUN_SCRIPTS.md](RUN_SCRIPTS.md).  
- **Already have GCS/BQ data:** [RUN_FROM_INTERMEDIATE.md](RUN_FROM_INTERMEDIATE.md).  
- **Exact commands and options:** [RUN_SCRIPTS.md](RUN_SCRIPTS.md).
