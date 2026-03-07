# dlt and Python Code: Step-by-Step with an Example

This guide explains **what dlt is**, **how our Python code uses it**, and **how one row of data** moves from a source (e.g. Kaggle CSV) to a Parquet file in GCS. One idea at a time, with a concrete example.

---

## Part 1: What is dlt?

**In one sentence:**  
**dlt** (data load tool) is a Python library that takes **rows you produce** (as dicts from a generator) and **writes them to a destination** (e.g. files on disk, GCS, BigQuery). It handles batching, file format (Parquet), and write mode (replace vs append).

**Why we use it:**  
We don’t want to write “open a file, write headers, serialize each row, flush, close” ourselves. We want to say: “here’s a stream of dicts; write them as Parquet to this GCS path.” dlt does that. So: **our code = produce rows; dlt = write them.**

**Three ideas in dlt:**

| Idea | Meaning in our project |
|------|------------------------|
| **Resource** | A Python generator that **yields** dicts (one per row). We have one resource: `jobs_resource`, which yields job rows. |
| **Pipeline** | A run that says: take this **resource**, send its data to this **destination**. We run one pipeline per source (e.g. Kaggle Data Engineer). |
| **Destination** | Where data lands. We use **filesystem** with a **GCS URL** (`gs://bucket/raw/...`), so “filesystem” here means **GCS**. |

So: **resource yields dicts → pipeline runs the resource → destination (GCS) gets Parquet files.**

---

## Part 2: The Big Picture (One Diagram)

```
You run:  python run_ingestion.py --source kaggle_data_engineer

  run_ingestion.py
       │
       ▼
  run_kaggle_data_engineer()  →  run_pipeline("horizon_kaggle_...", "kaggle_data_engineer_2023", stream_kaggle_data_engineer_2023)
       │
       ▼
  common.run_pipeline():
    1. Set DESTINATION__FILESYSTEM__BUCKET_URL = gs://bucket/raw/kaggle_data_engineer_2023
    2. Define jobs_resource() → yields one dict per row from stream_kaggle_data_engineer_2023()
    3. pipeline = dlt.pipeline(destination="filesystem", dataset_name=...)
    4. pipeline.run(jobs_resource(), loader_file_format="parquet")
       │
       ▼
  stream_kaggle_data_engineer_2023()  [in kaggle_data_engineer_2023.py]:
    - Download Kaggle CSV if needed
    - Read CSV in chunks (e.g. 10_000 rows)
    - For each row: _row_to_canonical() → RawJobRow → .to_load_dict() → add to batch
    - Yield batches of dicts
       │
       ▼
  dlt: consumes the stream of dicts, batches them, writes Parquet to GCS
```

So: **source (Kaggle)** → **stream function** (CSV → batches of dicts) → **resource** (yields each dict) → **dlt** (writes Parquet to GCS).

---

## Part 3: Step-by-Step Through the Code

### Step 1: You run the command

```bash
python run_ingestion.py --source kaggle_data_engineer
```

- **run_ingestion.py** parses `--source kaggle_data_engineer`, loads `.env`, checks `GCS_BUCKET` and `GOOGLE_CLOUD_PROJECT`.
- It looks up the runner for `kaggle_data_engineer` and calls **run_kaggle_data_engineer()**.

### Step 2: The runner calls the shared pipeline

**run_kaggle_data_engineer()** (in run_ingestion.py) does:

```python
from ingestion.pipelines.run_kaggle_data_engineer import run
run()
```

**run()** (in ingestion/pipelines/run_kaggle_data_engineer.py) does:

```python
return run_pipeline(
    PIPELINE_NAME="horizon_kaggle_data_engineer_2023",
    DATASET_NAME="kaggle_data_engineer_2023",
    stream_kaggle_data_engineer_2023,   # the function that will yield batches of rows
)
```

So the CLI only chooses *which* pipeline; the real logic is in **run_pipeline** and in the **stream function** you pass in.

### Step 3: run_pipeline sets the GCS path and defines the resource

**run_pipeline** (in ingestion/pipelines/common.py) does four things.

**3a. Build the GCS URL**

```python
bucket_base = get_gcs_base_url()   # e.g. gs://your-bucket/raw
bucket_url = f"{bucket_base.rstrip('/')}/{dataset_name}"   # gs://your-bucket/raw/kaggle_data_engineer_2023
os.environ["DESTINATION__FILESYSTEM__BUCKET_URL"] = bucket_url
```

dlt reads this environment variable when the destination is “filesystem”. So we tell dlt: “write files under this GCS path.”

**3b. Define the resource**

```python
@dlt.resource(name=TABLE_NAME, write_disposition="replace", columns=JOBS_COLUMNS)
def jobs_resource() -> Iterator[dict]:
    for batch in stream_fn():
        for row in batch:
            yield row
```

- **stream_fn** is the function we passed in (e.g. **stream_kaggle_data_engineer_2023**). It **yields batches** (lists of dicts).
- **jobs_resource** is a **generator**: it calls stream_fn(), then loops over each batch and **yields one dict at a time** to dlt.
- **@dlt.resource(...)** tells dlt: “this function is a data source; when you run the pipeline, pull from it.”
- **write_disposition="replace"** means: each run replaces the previous data (no appends).
- **columns=JOBS_COLUMNS** tells dlt the schema (field names and types) so it can write Parquet correctly.

**3c. Create the pipeline**

```python
pipeline = dlt.pipeline(
    pipeline_name=pipeline_name,
    destination="filesystem",
    dataset_name=dataset_name,
)
```

So we have a pipeline that writes to **filesystem** (GCS, because the URL is `gs://...`) and uses **dataset_name** in the path.

**3d. Run the pipeline**

```python
load_info = pipeline.run(jobs_resource(), loader_file_format="parquet")
```

- **jobs_resource()** returns the generator (it doesn’t run it yet).
- **pipeline.run(...)** starts the generator, pulls dicts from it, batches them, and writes **Parquet** files to the GCS path we set.
- When the generator is exhausted, dlt flushes the last batch and returns **load_info** (e.g. how many rows, which files).

So in one line: **run_pipeline** wires “stream function → resource → dlt → Parquet in GCS.”

### Step 4: Where do the dicts come from? The stream function

**stream_kaggle_data_engineer_2023()** (in ingestion/sources/kaggle_data_engineer_2023.py) does the following.

**4a. Download the dataset (if needed)**

```python
dest = Path(KAGGLE_BASE) / "lukkardata-data-engineer-job-postings-2023"
if force_download or not dest.exists():
    download_dataset(DATASET)
```

So the CSV (or CSVs) end up under `data/kaggle/lukkardata-data-engineer-job-postings-2023/`.

**4b. Find the main CSV**

```python
csv_path = _find_best_csv(dest)   # largest CSV in that folder
```

**4c. Read CSV in chunks**

```python
for chunk in pd.read_csv(csv_path, chunksize=batch_size, low_memory=False):
```

So we never load the whole file into memory; we process 10_000 rows at a time.

**4d. Map CSV columns to our canonical names**

On the first chunk we build **col_map**, e.g.:

- `Job_details` → `job_title`
- `Job_details.1` → `job_description`
- `Company_info` → `company_name`
- …

So we know which CSV column goes to which field in our schema.

**4e. Turn each row into a dict and add to a batch**

```python
for _, row in chunk.iterrows():
    canonical = _row_to_canonical(row, col_map)
    if canonical is None:
        continue
    batch.append(canonical.to_load_dict())
    if len(batch) >= batch_size:
        yield batch
        batch = []
```

- **_row_to_canonical(row, col_map)** builds a **RawJobRow** (see below).
- **canonical.to_load_dict()** turns that into a plain dict (dates/timestamps as strings) for dlt.
- When the batch is full, we **yield** it. So the stream function yields **lists of dicts**; the resource then yields **one dict at a time** from those lists.

So: **CSV row → RawJobRow → dict → batch → yielded to run_pipeline → jobs_resource yields each dict → dlt writes Parquet.**

### Step 5: The canonical shape (RawJobRow and JOBS_COLUMNS)

Every source (Kaggle, Hugging Face, etc.) maps its columns to the **same** shape so that downstream we have one consistent table.

**RawJobRow** (in ingestion/schema.py) is a Pydantic model with fields like:

- source_id, source_name  
- job_title, job_description, company_name, location  
- posted_date, job_url, skills, salary_info  
- ingested_at  

**JOBS_COLUMNS** (in the same file) tells dlt the types for each of these (text, date, timestamp, json). So every pipeline writes the same columns and types.

**to_load_dict()** does:

```python
return self.model_dump(mode="json")
```

So we get a dict with the same keys, and dates/timestamps are JSON-serializable (strings). That’s what dlt expects.

---

## Part 4: One Row, End to End (Example)

Suppose the Kaggle CSV has this row:

| Job_details   | Job_details.1   | Company_info | Job_details.4   |
|---------------|------------------|--------------|-----------------|
| Data Engineer | Build pipelines… | Acme Corp    | San Francisco   |

**1. Column map (from first chunk)**  
`Job_details` → job_title, `Job_details.1` → job_description, `Company_info` → company_name, `Job_details.4` → location_city (then we build `location` from city/state/country).

**2. _row_to_canonical(row, col_map)**  
Builds a **RawJobRow**:

- source_id = `"kaggle_data_engineer_2023"`
- job_title = `"Data Engineer"`
- job_description = `"Build pipelines…"`
- company_name = `"Acme Corp"`
- location = `"San Francisco"`
- posted_date = 2023-04-01 (default for this dataset)
- skills = e.g. `["Python", "SQL"]` if EXTRACT_SKILLS_TAXONOMY=1, else None
- ingested_at = now
- …

**3. to_load_dict()**  
Turns that into a dict, e.g.:

```python
{
    "source_id": "kaggle_data_engineer_2023",
    "job_title": "Data Engineer",
    "job_description": "Build pipelines…",
    "company_name": "Acme Corp",
    "location": "San Francisco",
    "posted_date": "2023-04-01",
    "skills": ["Python", "SQL"],
    "ingested_at": "2026-03-07T14:30:00",
    ...
}
```

**4. jobs_resource()**  
Yields this dict to dlt.

**5. dlt**  
Adds it to an internal batch. When the batch is full (or the stream ends), dlt writes one or more Parquet files under:

`gs://your-bucket/raw/kaggle_data_engineer_2023/jobs/...`

So **one CSV row → one RawJobRow → one dict → one row in a Parquet file** (and later one row in BigQuery when you run load_gcs_to_bigquery).

---

## Part 5: Summary Table

| Step | Where | What happens |
|------|--------|--------------|
| 1 | run_ingestion.py | Parse `--source`, load .env, call the right runner (e.g. run_kaggle_data_engineer). |
| 2 | run_kaggle_data_engineer.py | Call run_pipeline(name, dataset_name, stream_kaggle_data_engineer_2023). |
| 3 | common.run_pipeline | Set GCS URL; define jobs_resource (yields dicts from stream_fn); create dlt pipeline; run it with Parquet. |
| 4 | kaggle_data_engineer_2023.py | Download CSV; read in chunks; _row_to_canonical → RawJobRow → to_load_dict(); yield batches of dicts. |
| 5 | schema.py | RawJobRow = canonical shape; JOBS_COLUMNS = dlt schema; to_load_dict() = serialization for dlt. |
| 6 | dlt | Pull dicts from resource, batch them, write Parquet to GCS. |

**One sentence:**  
Our code **produces** rows (stream function → resource); dlt **writes** them (Parquet to GCS). The same pattern applies to every source; only the stream function (and thus the source of the rows) changes.

If you want to go deeper next, we can open **one** of these: (a) the exact dlt config (e.g. batch size, file naming), (b) how Hugging Face’s stream function differs from Kaggle’s, or (c) how load_gcs_to_bigquery reads these Parquet files and loads them into BigQuery.
