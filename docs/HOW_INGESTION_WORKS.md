# How `python run_ingestion.py --source kaggle_data_engineer` Works

Step-by-step flow with a concrete example of one row.

---

## In one sentence

The command runs a **single pipeline**: it downloads the Kaggle Data Engineer 2023 dataset (if needed), reads the CSV in chunks, converts each row into a **common job schema**, and uses **dlt** to write those rows as **Parquet files** into your **GCS bucket**.

---

## Step-by-step flow

### 1. You run the command

```bash
python run_ingestion.py --source kaggle_data_engineer
```

- **run_ingestion.py** is the entry point. It parses `--source kaggle_data_engineer`.
- It checks that **GCS_BUCKET** and **GOOGLE_CLOUD_PROJECT** (or GCP_PROJECT) are set. If either is missing, it exits with an error.
- It looks up the runner for `kaggle_data_engineer` and calls **run_kaggle_data_engineer()**.

---

### 2. The runner calls the shared pipeline

**run_kaggle_data_engineer()** (in `run_ingestion.py`) does:

```python
from ingestion.pipelines.run_kaggle_data_engineer import run
run()
```

**run()** (in `ingestion/pipelines/run_kaggle_data_engineer.py`) does:

```python
return run_pipeline(
    PIPELINE_NAME="horizon_kaggle_data_engineer_2023",
    DATASET_NAME="kaggle_data_engineer_2023",
    stream_kaggle_data_engineer_2023,   # the function that yields batches of rows
)
```

So the CLI only picks *which* pipeline; the real logic is in **run_pipeline** and the **stream function**.

---

### 3. run_pipeline sets up dlt and the GCS path

**run_pipeline** (in `ingestion/pipelines/common.py`) does:

1. **GCS URL**  
   - Calls **get_gcs_base_url()** from config → `gs://<GCS_BUCKET>/raw`.  
   - Builds **bucket_url** = `gs://<bucket>/raw/kaggle_data_engineer_2023`.  
   - Sets **DESTINATION__FILESYSTEM__BUCKET_URL** so dlt knows where to write.

2. **Resource**  
   - Defines a **jobs_resource()** generator: it calls **stream_kaggle_data_engineer_2023()**, gets batches of dicts, and **yields one dict per row** to dlt.  
   - The resource is declared with **write_disposition="replace"** and **columns=JOBS_COLUMNS** (the common schema).

3. **Pipeline run**  
   - Creates a dlt pipeline with **destination="filesystem"**, **dataset_name="kaggle_data_engineer_2023"**.  
   - Runs **pipeline.run(jobs_resource(), loader_file_format="parquet")**.  
   - dlt reads the stream of dicts and writes **Parquet files** under `gs://<bucket>/raw/kaggle_data_engineer_2023/`.

So: **stream function** → **batches of dicts** → **jobs_resource** yields one dict per row → **dlt** writes Parquet to GCS.

---

### 4. Where do the dicts come from? stream_kaggle_data_engineer_2023

**stream_kaggle_data_engineer_2023()** (in `ingestion/sources/kaggle_data_engineer_2023.py`) does:

1. **Download**  
   - Path = `data/kaggle/lukkardata-data-engineer-job-postings-2023` (or **KAGGLE_DATA_PATH** if set).  
   - If that folder doesn’t exist, it calls **download_dataset("lukkardata/data-engineer-job-postings-2023")** (Kaggle API, using `~/.kaggle/kaggle.json` or env vars).

2. **Find CSV**  
   - Finds the largest CSV in that folder (main data file).

3. **Read in chunks**  
   - Uses **pd.read_csv(..., chunksize=10_000)** so it doesn’t load the whole file into memory.

4. **Map columns**  
   - First chunk: ** _normalize_columns(chunk)** builds a mapping from CSV column names to our canonical names, e.g.  
     - `Job_details` → `job_title`  
     - `Job_details.1` → `job_description`  
     - `Company_info` → `company_name`  
     - etc.

5. **Each row → canonical → dict**  
   - For each row in the chunk:  
     - ** _row_to_canonical(row, col_map)** builds a **RawJobRow** (title, description, company, location, salary, optional skills if EXTRACT_SKILLS_TAXONOMY=1, etc.).  
     - **canonical.to_load_dict()** turns that into a plain dict (dates/timestamps serialized for dlt).  
   - Rows are appended to a **batch**; when the batch size is reached, the batch is **yielded** to the caller (run_pipeline → jobs_resource → dlt).

6. **End**  
   - When all chunks are done, any remaining rows are yielded. So the “stream” is a sequence of **lists of dicts** (batches).

---

## Example: one row through the pipeline

Suppose the Kaggle CSV has a row like:

| Job_details        | Job_details.1   | Company_info | Job_details.4 | ... |
|--------------------|------------------|--------------|---------------|-----|
| Data Engineer      | Build pipelines… | Acme Corp    | San Francisco | ... |

1. **Column map** (from first chunk):  
   `Job_details` → `job_title`, `Job_details.1` → `job_description`, `Company_info` → `company_name`, `Job_details.4` → `location_city`, etc.

2. ** _row_to_canonical** builds a **RawJobRow**:  
   - source_id = `"kaggle_data_engineer_2023"`  
   - job_title = `"Data Engineer"`  
   - job_description = `"Build pipelines…"`  
   - company_name = `"Acme Corp"`  
   - location = `"San Francisco"` (or city/state/country combined)  
   - posted_date = 2023-04-01 (default for this dataset)  
   - skills = list of strings if EXTRACT_SKILLS_TAXONOMY=1, else None  
   - ingested_at = now  
   - etc.

3. **to_load_dict()** turns that into something like:  
   `{"source_id": "kaggle_data_engineer_2023", "job_title": "Data Engineer", "job_description": "Build pipelines…", "company_name": "Acme Corp", "location": "San Francisco", "posted_date": "2023-04-01", "skills": ["Python", "SQL"], ...}`  
   (dates as strings, no Python objects.)

4. **jobs_resource()** yields this dict to **dlt**.

5. **dlt** batches many such dicts and writes them as **Parquet** under  
   `gs://<your-bucket>/raw/kaggle_data_engineer_2023/jobs/...`.

So one CSV row becomes one dict, then one row in a Parquet file (and later in BigQuery after you run **load_gcs_to_bigquery.py**).

---

## Summary

| Step | Where | What happens |
|------|--------|--------------|
| 1 | run_ingestion.py | Parse `--source kaggle_data_engineer`, check GCS_BUCKET and GOOGLE_CLOUD_PROJECT, call run_kaggle_data_engineer(). |
| 2 | run_kaggle_data_engineer.py | Call run_pipeline(..., stream_kaggle_data_engineer_2023). |
| 3 | common.py | Set GCS URL, define jobs_resource() that yields dicts from stream_fn(), run dlt pipeline → Parquet to GCS. |
| 4 | kaggle_data_engineer_2023.py | Download Kaggle dataset if needed, read CSV in chunks, map columns, _row_to_canonical → RawJobRow → to_load_dict(), yield batches of dicts. |

**Data path:** Kaggle CSV → RawJobRow (canonical schema) → dict → dlt → Parquet in GCS.
