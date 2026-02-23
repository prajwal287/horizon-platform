# dlt (data load tool) — Learn the Top 20% Fast

A short, Pareto-style guide: **what dlt is**, **why use it**, **the 20% that gives 80% of the value**, **how it differs from other tools**, and **core concepts with real examples from this repo**.

---

## 1. What is dlt?

**dlt** (data load tool) is an **open-source Python library** for loading data from sources (APIs, files, DBs) into destinations (BigQuery, Snowflake, GCS, filesystem, etc.). You write **Python** that yields rows; dlt handles **schema inference/declaration**, **batching**, **writing**, and **state** (incremental loads).

- **Official**: [dlthub.com](https://dlthub.com)  
- **GitHub**: [dlt-hub/dlt](https://github.com/dlt-hub/dlt)

**In one sentence**: *“Extract in your code; dlt does the load (and a lot of the transform plumbing).”*

---

## 2. Why study dlt?

| Reason | Why it matters |
|--------|----------------|
| **Python-native** | No YAML-only or low-code lock-in; full control and testability. |
| **Schema as code** | You declare or infer schema; dlt validates and writes (Parquet, BQ, etc.) correctly. |
| **Idempotency & incremental** | Built-in `write_disposition` and state so re-runs don’t duplicate data. |
| **Scalable** | Streams/batches; works with 500k+ rows (like your job postings). |
| **One pipeline, many destinations** | Same resource can go to filesystem (GCS), BigQuery, Snowflake, etc. |
| **Widely used** | Common in modern data stacks (dbt, Airbyte, reverse-ETL tools integrate or mirror concepts). |

---

## 3. Pareto: the top 20% you need

If you learn **only** these, you’ll cover most real use cases:

1. **Resource** — A Python generator that yields rows (dicts). dlt consumes it and writes to the destination.
2. **Pipeline** — A named run: one pipeline = one destination + one or more resources.
3. **Destination** — Where data lands: `filesystem` (e.g. GCS), `bigquery`, `snowflake`, etc.
4. **Write disposition** — `replace` (overwrite table) vs `append` (add rows) vs `merge` (upsert).
5. **Schema (columns)** — Declare column names and types so dlt writes correct Parquet/BigQuery types.

Everything else (incremental state, normalizers, hints) builds on these five.

---

## 4. How dlt differs from other tools

| Tool | Model | Best for | dlt difference |
|------|--------|----------|-----------------|
| **Airbyte / Fivetran** | Connector-based (prebuilt sources → destinations) | Fast setup, managed connectors | dlt = **code-first**: you write the “source” (Python), dlt does load + schema; more flexible, no connector limit. |
| **Custom Python (pandas + to_parquet)** | You do everything | Full control, one-off scripts | dlt = **schema + batching + state** for you; same “I write Python” feel, less boilerplate and fewer bugs. |
| **Spark / Beam** | Distributed compute | Huge data, complex DAGs | dlt = **single-process**, simpler; use when you don’t need a cluster. |
| **dbt** | SQL transforms in warehouse | Transform after load | dlt = **load**; dbt = **transform**. They pair: dlt → GCS/BQ, then dbt on BQ. |

**When to choose dlt**: You want a **Python-defined pipeline**, **explicit schema**, **idempotent loads**, and **one codebase** that can target GCS, BigQuery, or others without rewriting logic.

---

## 5. Core concepts with examples (from this repo)

### 5.1 Resource = “something that yields rows”

A **resource** is a function (or generator) that yields **dicts**. dlt will batch them and write to the destination.

**From** `ingestion/pipelines/run_kaggle_data_engineer.py`:

```python
@dlt.resource(name=TABLE_NAME, write_disposition="replace", columns=JOBS_COLUMNS)
def jobs_resource() -> Iterator[dict]:
    for batch in stream_kaggle_data_engineer_2023():
        for row in batch:
            yield row
```

- `name=TABLE_NAME` → table (or file prefix) name at destination.
- `write_disposition="replace"` → overwrite that table each run (idempotent full refresh).
- `columns=JOBS_COLUMNS` → schema (see below).
- Your source (`stream_kaggle_data_engineer_2023()`) can be **anything** that yields rows (CSV chunks, API pages, DB cursor); dlt doesn’t care.

**Real-world idea**: The “extract” is your code; the “load” is dlt.

---

### 5.2 Pipeline = one run to one destination

You create a **pipeline** with a **name**, **destination**, and **dataset**. Then you `run()` one or more resources.

**From the same file**:

```python
pipeline = dlt.pipeline(
    pipeline_name=PIPELINE_NAME,
    destination="filesystem",
    dataset_name=DATASET_NAME,
)
load_info = pipeline.run(jobs_resource(), loader_file_format="parquet")
```

- `destination="filesystem"` → write to a path; in your case the path is **GCS** (`gs://bucket/raw/...`).
- `dataset_name` → subfolder/prefix (e.g. `kaggle_data_engineer_2023`).
- `loader_file_format="parquet"` → output format.

**Real-world idea**: Same `jobs_resource()` could be run with `destination="bigquery"` later; only config changes.

---

### 5.3 Destination = where data lands

In Horizon you use **filesystem** with a **GCS URL**:

```python
# ingestion/config.py → get_gcs_base_url() → gs://BUCKET/raw
os.environ["DESTINATION__FILESYSTEM__BUCKET_URL"] = bucket_url  # gs://bucket/raw/kaggle_data_engineer_2023
pipeline = dlt.pipeline(..., destination="filesystem", dataset_name=DATASET_NAME)
```

So “filesystem” here = **GCS**. dlt uses your GCP credentials and writes Parquet there.

**Other common destinations**: `bigquery`, `snowflake`, `redshift`, `duckdb`, etc. Same resource, different destination.

---

### 5.4 Write disposition = overwrite vs append vs merge

| Value | Meaning | When to use |
|-------|--------|-------------|
| `replace` | Drop and recreate table (or replace files) | Full refresh, idempotent (your current pattern). |
| `append` | Add rows every run | Event streams, logs; watch for duplicates. |
| `merge` | Upsert by key | Deduplication, SCD-type loads. |

Your pipelines use `replace` so each run overwrites the previous table — safe and simple for batch loads.

---

### 5.5 Schema (columns)

You pass a **columns** dict so dlt knows types and names (and can write correct Parquet/BigQuery types):

**From** `run_kaggle_data_engineer.py`:

```python
JOBS_COLUMNS = {
    "source_id": {"data_type": "text"},
    "source_name": {"data_type": "text"},
    "job_title": {"data_type": "text"},
    "job_description": {"data_type": "text"},
    "company_name": {"data_type": "text"},
    "location": {"data_type": "text"},
    "posted_date": {"data_type": "date"},
    "job_url": {"data_type": "text"},
    "skills": {"data_type": "json"},
    "salary_info": {"data_type": "text"},
    "ingested_at": {"data_type": "timestamp"},
}
```

**Real-world idea**: Without this, dlt infers types; with it, you avoid surprises (e.g. dates as strings) and stay consistent across runs.

---

## 6. End-to-end flow in Horizon (recap)

1. **Source** (e.g. `ingestion/sources/kaggle_data_engineer_2023.py`): Download CSV, normalize, filter, yield **batches of dicts**.
2. **Resource** (e.g. `jobs_resource`): Generator that yields those dicts; decorated with `@dlt.resource(..., write_disposition="replace", columns=...)`.
3. **Pipeline**: `dlt.pipeline(destination="filesystem", dataset_name=...)` with `DESTINATION__FILESYSTEM__BUCKET_URL=gs://...`.
4. **Run**: `pipeline.run(jobs_resource(), loader_file_format="parquet")` → dlt writes Parquet to GCS.
5. **Step 2** (outside dlt): `scripts/load_gcs_to_bigquery.py` loads that Parquet into BigQuery.

So: **dlt = “source → GCS (Parquet)”**; your script = “GCS → BigQuery”.

---

## 7. Quick learning path

1. **Read one pipeline**  
   Open `ingestion/pipelines/run_kaggle_data_engineer.py` and follow: resource → pipeline → run.

2. **Run it**  
   Set `GCS_BUCKET`, `GOOGLE_APPLICATION_CREDENTIALS`, then:  
   `python run_ingestion.py --source kaggle_data_engineer`  
   Check GCS for Parquet under `gs://BUCKET/raw/kaggle_data_engineer_2023/`.

3. **Change one thing**  
   e.g. add a column to `JOBS_COLUMNS` and a field in the dict your source yields; re-run and inspect Parquet/BQ.

4. **Try another destination**  
   In a branch or copy, switch to `destination="bigquery"` and run (with BQ credentials) to see the same resource land in BigQuery.

5. **Optional**  
   Skim [dlt docs](https://dlthub.com/docs) for: incremental loading, merge, and custom normalizers when you need them.

---

## 8. Summary

| Concept | One-line takeaway |
|--------|--------------------|
| **dlt** | Python load layer: you yield rows, dlt handles schema, batching, and writing. |
| **Resource** | Generator of dicts + `@dlt.resource(name, write_disposition, columns)`. |
| **Pipeline** | Named run: destination + dataset + one or more resources. |
| **Destination** | Where data goes (e.g. filesystem = GCS, or bigquery). |
| **Write disposition** | replace / append / merge. |
| **Schema (columns)** | Dict of column name → `{ "data_type": "text" \| "date" \| "timestamp" \| "json" \| ... }`. |

Master these and you’re in the top 20% of what you need to use dlt effectively in projects like Horizon.
