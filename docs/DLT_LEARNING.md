# Learning dlt through this project

This document explains **how [dlt](https://dlthub.com/docs) is used in Horizon** so you can learn dlt concepts in context. It combines:

- A **short primer** (resource, pipeline, destination)
- The **end-to-end scenario** (CLI → stream → dlt → GCS → BigQuery)
- **Deep dives**: (1) Hugging Face vs Kaggle sources, (3) `replace` + multiple Parquet files

**Related:** [HOW_IT_WORKS.md](HOW_IT_WORKS.md) · [RUN_SCRIPTS.md](RUN_SCRIPTS.md) · `ingestion/pipelines/common.py`

---

## Part A — What dlt is (in one project-shaped sentence)

**dlt takes rows your Python code yields and loads them into a destination** (here: **Parquet files on GCS**), handling batching, format, and load disposition.

Horizon splits the stack:

| Step | Tool | Role |
|------|------|------|
| **1** | **dlt** | Dict rows → **Parquet** under `gs://<bucket>/raw/<dataset_name>/` |
| **2** | **`load_gcs_to_bigquery.py`** | All matching Parquet URIs → **one BigQuery table** (`WRITE_TRUNCATE`) |

dlt does **not** load BigQuery in this repo’s step 1; that is intentional (lake-first, simple BQ loads).

---

## Part B — dlt vocabulary (mapped to this codebase)

| Concept | Meaning | Where in Horizon |
|--------|---------|-------------------|
| **Resource** | A named stream of rows (often a generator). Tells dlt the logical **table** name, **columns** hints, and **write disposition**. | `jobs_resource()` in `ingestion/pipelines/common.py` — `@dlt.resource(name="jobs", ...)` |
| **Pipeline** | Runnable object: **destination** + **dataset name** + run of one or more resources. | `dlt.pipeline(pipeline_name=..., destination="filesystem", dataset_name=...)` |
| **Destination** | Where data lands. `"filesystem"` + `gs://...` = **GCS as a file layout**. | `DESTINATION__FILESYSTEM__BUCKET_URL` env set before `pipeline.run()` |
| **Stream function** | Your code: **yields batches** of `dict` rows (not dlt-specific; project convention). | e.g. `stream_kaggle_data_engineer_2023`, `stream_huggingface_data_jobs` |
| **`columns=`** | Schema hints (types) for the resource. | `JOBS_COLUMNS` from `ingestion/schema.py` |
| **`write_disposition="replace"`** | New load **replaces** previous data for that resource (full refresh semantics). | On `@dlt.resource(...)` in `common.py` |

---

## Part C — The shared pattern: `run_pipeline()`

All sources go through **one** function:

```18:41:ingestion/pipelines/common.py
def run_pipeline(
    pipeline_name: str,
    dataset_name: str,
    stream_fn: Callable[[], Iterator[list[dict]]],
) -> dlt.Pipeline:
    """Run one dlt pipeline: stream_fn() yields batches → dlt writes Parquet to gs://bucket/raw/<dataset_name>/ (replace)."""
    bucket_base = get_gcs_base_url()
    bucket_url = f"{bucket_base.rstrip('/')}/{dataset_name}"
    os.environ["DESTINATION__FILESYSTEM__BUCKET_URL"] = bucket_url

    @dlt.resource(name=TABLE_NAME, write_disposition="replace", columns=JOBS_COLUMNS)
    def jobs_resource() -> Iterator[dict]:
        for batch in stream_fn():
            for row in batch:
                yield row

    pipeline = dlt.pipeline(
        pipeline_name=pipeline_name,
        destination="filesystem",
        dataset_name=dataset_name,
    )
    load_info = pipeline.run(jobs_resource(), loader_file_format="parquet")
    logger.info("Pipeline %s load_info: %s", pipeline_name, load_info)
    return pipeline
```

**Read this as:**

1. Build **GCS base path**: `gs://<GCS_BUCKET>/raw/<dataset_name>/` (via `get_gcs_base_url()` + `dataset_name`).
2. Tell dlt’s filesystem destination that URL (`DESTINATION__FILESYSTEM__BUCKET_URL`).
3. Define a **resource** `jobs` that:
   - Calls your `stream_fn()` (e.g. Hugging Face or Kaggle),
   - Flattens **batch → single rows** with `yield row` (dlt consumes a stream of rows).
4. **Run** the pipeline with **Parquet** as the file format.
5. Log `load_info` (useful when debugging dlt).

---

## Part D — End-to-end scenario: `run_ingestion.py --source kaggle_data_engineer`

Use this as your **mental replay** of a full run.

| Step | What happens |
|------|----------------|
| **D1** | You run `python run_ingestion.py --source kaggle_data_engineer` (or Docker equivalent). |
| **D2** | `run_ingestion.py` checks `GCS_BUCKET` and `GOOGLE_CLOUD_PROJECT`, then calls `run_kaggle_data_engineer()`. |
| **D3** | `ingestion/pipelines/run_kaggle_data_engineer.py` calls `run_pipeline(PIPELINE_NAME, "kaggle_data_engineer_2023", stream_kaggle_data_engineer_2023)`. |
| **D4** | **Not dlt:** `stream_kaggle_data_engineer_2023()` downloads/opens the Kaggle CSV, reads **pandas chunks**, maps columns → `RawJobRow`, `to_load_dict()`, **yields lists of dicts** (batches). |
| **D5** | **dlt:** `jobs_resource()` pulls those batches and **yields one dict per job** to the pipeline. |
| **D6** | **dlt:** `pipeline.run(..., loader_file_format="parquet")` writes **Parquet** under `gs://<bucket>/raw/kaggle_data_engineer_2023/` with **`replace`** semantics for the `jobs` resource. |
| **D7** | **Not dlt:** Later, `python scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer` globs `**/*.parquet` under that prefix and loads into `raw_kaggle_data_engineer_2023`. |

**Takeaway:** dlt’s boundary is **“canonical dict rows → files on GCS.”** Everything before that is **your extractor**; everything after is **your BQ loader**.

---

## Part 1 (deep dive) — Hugging Face vs Kaggle: two ways to feed the same dlt resource

Both sources use the **same** dlt wiring (`run_pipeline` + `jobs` resource). The **only** difference is **how `stream_fn` produces batches**.

### 1.1 Kaggle Data Engineer: **CSV on disk, chunked with pandas**

**File:** `ingestion/sources/kaggle_data_engineer_2023.py`

- Ensures data exists (Kaggle API download into `data/kaggle/...` if needed).
- Opens a **local CSV** with `pd.read_csv(..., chunksize=batch_size)`.
- Each chunk: map columns → `_row_to_canonical` → `RawJobRow.to_load_dict()`.
- **Yields:** `List[dict]` per chunk (e.g. up to 10,000 rows).

**Mental model:** *File-based ETL* — bounded by disk + pandas; memory stays controlled via **chunking**.

```text
CSV file → pandas chunks → filter/map → batch of dicts → yield
                                              ↓
                              jobs_resource() yields row-by-row → dlt → Parquet on GCS
```

### 1.2 Hugging Face: **HF `datasets`, row iteration (not “streaming download” in the dlt sense)**

**File:** `ingestion/sources/huggingface_data_jobs.py`

- Calls `load_dataset("lukebarousse/data_jobs", split="train", trust_remote_code=True)`.
- Iterates **`for ... in ds:`** over the dataset (Hugging Face may **cache** Arrow data locally after first fetch; you are not reading a CSV path in *your* code).
- Each row: `_row_to_canonical` applies **date** + **data-domain** filters; builds `RawJobRow`, `to_load_dict()`.
- **Yields:** batches of dicts when `len(batch) >= batch_size` (same 10k pattern as Kaggle).

**Mental model:** *Dataset iterator* — the `datasets` library abstracts storage/streaming; you still present **batches** to dlt the same way.

```text
HF hub / cache → Dataset rows → filter/map → batch of dicts → yield
                                                    ↓
                                jobs_resource() → dlt → Parquet on GCS
```

### 1.3 Side-by-side

| Aspect | Kaggle (`stream_kaggle_data_engineer_2023`) | Hugging Face (`stream_huggingface_data_jobs`) |
|--------|---------------------------------------------|-----------------------------------------------|
| **Primary library** | `pandas` + local CSV | `datasets.load_dataset` |
| **Input** | File path under `data/kaggle/...` | HF dataset object (`split="train"`) |
| **Batching** | Natural: `chunksize` from `read_csv` | Manual: append rows until `batch_size`, then yield |
| **dlt sees** | Same: iterator of **lists of dicts** flattened to row dicts | Same |
| **Pipeline module** | `run_kaggle_data_engineer.py` | `run_huggingface.py` |
| **`dataset_name` / GCS folder** | `kaggle_data_engineer_2023` | `huggingface_data_jobs` |

**Important:** Neither source “pushes” data into dlt differently — both conform to **`stream_fn(): Iterator[list[dict]]`**, then `common.py` normalizes to **per-row** yields for dlt.

### 1.4 Scenario: “I only want to learn dlt — which source should I trace?”

1. Read **`ingestion/pipelines/common.py`** (dlt only).
2. Pick **one** stream:
   - Prefer **Kaggle** if you like **file + pandas** mental models.
   - Prefer **Hugging Face** if you like **dataset APIs** and filters.

Then run **one** pipeline:

```bash
export GCS_BUCKET=...
export GOOGLE_CLOUD_PROJECT=...
python run_ingestion.py --source kaggle_data_engineer
# or
python run_ingestion.py --source huggingface
```

Inspect GCS: `gsutil ls -r gs://$GCS_BUCKET/raw/<dataset_name>/ | head`

---

## Part 3 (deep dive) — `write_disposition="replace"` and multiple Parquet files

### 3.1 Why you see **multiple Parquet files** in **one** run

During a **single** `pipeline.run(...)`:

- dlt streams many rows through the `jobs` resource.
- The **loader** writes **Parquet**; for scale and internals, output is often **split across multiple files** (parts, not one giant file).

That is **normal**: one logical load can produce **N Parquet objects** under the pipeline’s layout.

**Analogy:** one database “bulk load” might still use multiple files on disk — same idea.

### 3.2 What **`replace`** means (conceptually)

For this project’s usage:

- **`replace`** on the resource means: this run is a **full refresh** of that resource’s data for the pipeline — you are **not** appending incrementally inside dlt for `jobs`.
- Practically: **each successful ingestion run** should give you a **coherent snapshot** of jobs for that source, not duplicate rows **from dlt’s load semantics** for that replace load.

**Operational note:** dlt and the filesystem destination may evolve **exact folder layout** between versions. Always treat **`load_gcs_to_bigquery.py`** as the contract: it loads **all** `**/*.parquet` under `raw/<source_suffix>/`. If you upgrade dlt, **verify** GCS listing still matches expectations.

### 3.3 How BigQuery load ties in (multiple URIs → one table)

**File:** `scripts/load_gcs_to_bigquery.py`

- Builds a glob: `gs://{bucket}/raw/{suffix}/**/*.parquet`.
- Collects **all** matching URIs.
- Calls `load_table_from_uri(uris, table_ref, ...)` with **`WRITE_TRUNCATE`**.

So:

| Layer | Behavior |
|-------|-----------|
| **dlt** | Writes **one or more** Parquet files for the run (typical). |
| **BigQuery loader** | Reads **all** those files in **one load job** and **replaces** the destination table. |

**Scenario — “Did BQ double-count because there were 5 Parquet files?”**

No — BigQuery loads **all URIs into one table** for that job; row count is the **sum of rows in those files** (and those files should together represent **one** dlt load snapshot, not five unrelated full copies). If you ever see duplicate-looking data, debug **upstream** (e.g. running load twice without truncate, or stale extra Parquet left under the prefix from manual copies).

### 3.4 Scenario — “I run ingestion twice on the same day”

1. **First run:** dlt `replace` load → Parquet set A on GCS → BQ `WRITE_TRUNCATE` → table matches A.
2. **Second run:** dlt `replace` load → Parquet set B on GCS → BQ `WRITE_TRUNCATE` → table matches B.

You should **not** expect row-level merge; you expect **latest full snapshot wins** in BigQuery.

### 3.5 Incremental loads (not how this repo uses dlt today)

If later you need **append** or **merge** (SCD2, dedupe by `job_id`), you would:

- Change **dlt** disposition / strategy **or**
- Land raw with replace but maintain **Silver** tables in BigQuery/dbt with incremental logic.

That is **out of scope** for the current `common.py` pattern but is the usual next step in a lakehouse.

---

## Part E — Quick exercises (optional)

1. **Trace Hugging Face:** From `run_huggingface.py` → `stream_huggingface_data_jobs` → list which fields map to `RawJobRow`.
2. **Trace GCS path:** For Hugging Face, confirm `dataset_name` → folder under `raw/` matches `SOURCE_TO_GCS_AND_TABLE` in `load_gcs_to_bigquery.py`.
3. **Observe Parquet count:** After one run, count Parquet files under one `raw/<name>/` prefix and relate to **one** BQ load with multiple URIs.

---

## Part F — Official dlt docs (read next)

- [Getting started](https://dlthub.com/docs/intro)
- [Resources](https://dlthub.com/docs/general-usage/resource)
- [Pipeline](https://dlthub.com/docs/general-usage/pipeline)
- [Filesystem & cloud storage](https://dlthub.com/docs/dlt-ecosystem/destinations/filesystem) (GCS via `gs://`)

---

## Glossary (Horizon-specific)

| Term | Definition |
|------|------------|
| **`stream_fn`** | Callable with no args returning an iterator of **batches** (`list[dict]`). |
| **`dataset_name`** | dlt dataset segment + folder name under `gs://.../raw/`. |
| **`jobs`** | dlt resource (table) name; all sources write the same column set via `JOBS_COLUMNS`. |
| **Step 1 / Step 2** | Step 1 = dlt → GCS; Step 2 = script → BigQuery. |

---

*This doc is tailored to the Horizon codebase. For behavior details when you upgrade dlt, cross-check the version in `requirements.txt` with the official dlt docs for that version.*
