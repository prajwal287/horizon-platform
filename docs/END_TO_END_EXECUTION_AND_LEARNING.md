# End-to-End Execution & Learning Guide

This doc explains **where the system starts**, **how execution flows**, and **how the pieces connect**. Use it to build mental models, debug failures, and grow toward senior/staff data engineer thinking.

---

## 1. The Big Picture: Where It Starts and How It Ends

**Entry point:** You run **one of two main flows** (or both).

| Flow | Entry point | What it does | End state |
|------|-------------|---------------|-----------|
| **Ingestion (Step 1)** | `run_ingestion.py --source <name>` | dlt pipelines read sources (Kaggle/Hugging Face), normalize to a canonical schema, write **Parquet to GCS** | Parquet under `gs://<bucket>/raw/<source_slug>/` |
| **Load to BigQuery (Step 2)** | `scripts/load_gcs_to_bigquery.py --source <name>` | Reads Parquet from GCS, loads into BigQuery **raw_*** tables | Tables like `raw_kaggle_data_engineer_2023` in dataset `job_market_analysis` |

**Optional / analytical:**

- **Master table:** `scripts/create_master_table.py` — builds a **view** (or materialized table) that unions all `raw_*` tables → single `master_jobs` for analytics.
- **Skills comparison:** `scripts/compare_skills_extraction.py` — **evaluation only**; compares taxonomy vs LLM skills on a sample (CSV or BigQuery). Does not change ingested data.

So: **ingestion** and **load_gcs_to_bigquery** are the core pipeline. Everything else (master table, compare script) runs on top of that.

---

## 2. End-to-End Execution Flow (Step by Step)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  YOU RUN (from project root)                                                     │
│  python run_ingestion.py --source kaggle_data_engineer                           │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  run_ingestion.py                                                                │
│  • Checks GCS_BUCKET, GOOGLE_CLOUD_PROJECT                                       │
│  • Dispatches to runner: run_kaggle_data_engineer()                             │
│  • Imports: ingestion.pipelines.run_kaggle_data_engineer → run()                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ingestion/pipelines/run_kaggle_data_engineer.py (+ common.run_pipeline)         │
│  • run_pipeline() sets DESTINATION__FILESYSTEM__BUCKET_URL = gs://.../raw/...   │
│  • Builds dlt resource "jobs" (replace, columns = JOBS_COLUMNS from schema.py)   │
│  • jobs_resource() yields dicts from stream_kaggle_data_engineer_2023()          │
│  • pipeline.run(jobs_resource(), loader_file_format="parquet")                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ingestion/sources/kaggle_data_engineer_2023.py                                  │
│  • stream_kaggle_data_engineer_2023():                                           │
│    1. Download Kaggle dataset (if not present) via kaggle_download.download_...   │
│    2. Find largest CSV in data/kaggle/lukkardata-data-engineer-job-postings-2023 │
│    3. pd.read_csv(..., chunksize=10_000) → for each chunk:                        │
│       - _normalize_columns(chunk) → map CSV columns to canonical names            │
│       - For each row: _row_to_canonical(row, col_map) → RawJobRow | None           │
│       - If EXTRACT_SKILLS_TAXONOMY=1: extract_skills_taxonomy(title, desc)        │
│       - canonical.to_load_dict() → append to batch; yield batch when full         │
│  • Each yielded batch is a list of dicts (one per job row)                        │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │  ingestion/skills_extraction.py        │
                    │  (only if EXTRACT_SKILLS_TAXONOMY=1)   │
                    │  extract_skills_taxonomy(title, desc)  │
                    │  → regex match DATA_ENGINEER_SKILLS     │
                    │  → canonical names via ALIASES → list   │
                    └───────────────────┴───────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ingestion/schema.py — RawJobRow                                                 │
│  • Canonical shape: source_id, job_title, job_description, company_name,        │
│    location, posted_date, job_url, skills (list), salary_info, ingested_at       │
│  • to_load_dict() → dict for dlt (dates/timestamps serialized)                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  dlt (data load tool)                                                            │
│  • Consumes the iterator from jobs_resource()                                    │
│  • Writes to "filesystem" destination (GCS) as Parquet                           │
│  • Path: gs://<bucket>/raw/kaggle_data_engineer_2023/jobs/*.parquet               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                          STEP 1 DONE — Parquet in GCS
                                        │
┌─────────────────────────────────────────────────────────────────────────────────┐
│  YOU RUN                                                                         │
│  python scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer             │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  scripts/load_gcs_to_bigquery.py                                                 │
│  • SOURCE_TO_GCS_AND_TABLE["kaggle_data_engineer"] = (gcs_suffix, bq_table)      │
│  • prefix = "raw/kaggle_data_engineer_2023/"                                      │
│  • gcsfs.glob("gs://<bucket>/raw/.../**/*.parquet") → list of URIs               │
│  • bigquery.Client().load_table_from_uri(uris, project.dataset.raw_...)           │
│    WRITE_TRUNCATE, PARQUET, autodetect=True                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  BigQuery                                                                        │
│  Tables: raw_huggingface_data_jobs, raw_kaggle_data_engineer_2023, ...           │
│  Optional: create_master_table.py → view/table master_jobs (UNION ALL)           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Files and Their Roles

| File | Role |
|------|------|
| **run_ingestion.py** | CLI entry; validates env (GCS_BUCKET, GOOGLE_CLOUD_PROJECT); dispatches to pipeline runners. |
| **ingestion/config.py** | GCS bucket, prefix, BigQuery dataset, cutoff date, **DATA_ENGINEER_SKILLS** / **DATA_ENGINEER_SKILL_ALIASES** for taxonomy. |
| **ingestion/schema.py** | **RawJobRow** (Pydantic): single canonical shape for all sources; `to_load_dict()` for dlt. |
| **ingestion/sources/kaggle_data_engineer_2023.py** | Kaggle DE source: download, CSV chunking, column mapping, **RawJobRow** per row, optional taxonomy skills. |
| **ingestion/sources/kaggle_download.py** | Shared Kaggle API: `download_dataset()`, `KAGGLE_BASE`; requires KAGGLE_USERNAME + KAGGLE_KEY. |
| **ingestion/skills_extraction.py** | **Taxonomy:** regex over title/description using config skills/aliases. **LLM:** Gemini single/batch (used by compare script, not by ingestion unless you add it). |
| **ingestion/pipelines/run_*.py** | Each defines a dlt pipeline: destination URL, resource(s), `pipeline.run()`. |
| **scripts/load_gcs_to_bigquery.py** | Step 2: GCS Parquet → BigQuery raw_* (WRITE_TRUNCATE). |
| **scripts/create_master_table.py** | CREATE OR REPLACE VIEW master_jobs (UNION ALL of raw_*). |
| **scripts/compare_skills_extraction.py** | Evaluation: sample from CSV or BigQuery → taxonomy + optional LLM → CSV + metrics. |

---

## 4. How Skills Extraction Fits In

- **At ingest time (optional):**  
  Set `EXTRACT_SKILLS_TAXONOMY=1` (or `true`). Then in `kaggle_data_engineer_2023._row_to_canonical()`, the code calls `extract_skills_taxonomy(title, desc)` and puts the result in `RawJobRow.skills`. That flows into Parquet and then BigQuery. No Gemini is used here.

- **Evaluation only (compare script):**  
  `compare_skills_extraction.py` loads a sample (CSV or BigQuery), runs **taxonomy** on every row, and optionally **LLM (Gemini)** in batches. It writes a comparison CSV and metrics (e.g. Jaccard). This does **not** write back into the lake; it helps you decide whether to rely on taxonomy, LLM, or a hybrid.

So: **ingestion** can optionally add **taxonomy** skills; **LLM** is only used in the **compare** script unless you extend the ingestion code.

---

## 5. Environment Variables You Care About

| Variable | Used by | Purpose |
|----------|---------|--------|
| **GCS_BUCKET** | run_ingestion, load_gcs_to_bigquery | Where Parquet lives; where BQ loader reads from. |
| **GOOGLE_CLOUD_PROJECT** or **GCP_PROJECT** | run_ingestion, load_gcs_to_bigquery, create_master_table, compare --from-bigquery | GCP project for BQ and GCS. |
| **BIGQUERY_DATASET** | config, load_gcs_to_bigquery, create_master_table, compare --from-bigquery | Dataset name (default `job_market_analysis`). |
| **KAGGLE_USERNAME**, **KAGGLE_KEY** (or **KAGGLE_API_TOKEN**) | kaggle_download, Kaggle sources | Kaggle API auth for download. |
| **EXTRACT_SKILLS_TAXONOMY** | kaggle_data_engineer_2023 | Set to `1`/`true` to fill `skills` at ingest via taxonomy. |
| **GOOGLE_API_KEY** (or **GEMINI_API_KEY**) | compare_skills_extraction (when not --skip-llm), skills_extraction LLM functions | Gemini for LLM skills extraction in compare script. |

---

## 6. Execution Checklist (Minimal Path to “Data in BQ”)

1. **Env**
   - `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT` (or `GCP_PROJECT`).
   - For Kaggle: `KAGGLE_USERNAME`, `KAGGLE_KEY` (or `KAGGLE_API_TOKEN`).
   - `gcloud auth application-default login` so GCS/BQ work.

2. **Step 1 — Ingest to GCS**
   - `python run_ingestion.py --source kaggle_data_engineer`  
   - Optional: `EXTRACT_SKILLS_TAXONOMY=1` to get taxonomy skills in the data.

3. **Step 2 — Load to BigQuery**
   - `python scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer`

4. **Optional**
   - `python scripts/create_master_table.py` for `master_jobs` view.
   - `python scripts/compare_skills_extraction.py --from-bigquery --sample 100 --print-metrics` (and set `GOOGLE_API_KEY` if you want LLM comparison).

---

## 7. Learning and Staff-Level Thinking

Use these to build depth and “scar tissue” while you implement.

- **Idempotency**  
  Step 1 uses dlt `write_disposition="replace"`; Step 2 uses `WRITE_TRUNCATE`. So re-running the same source overwrites; no duplicate rows from re-runs. Ask: “If I run this twice, do I get 2x rows or the same snapshot?”

- **Schema contract**  
  All sources map into **RawJobRow**. That gives one contract for Silver/Gold and keeps downstream SQL (e.g. `master_jobs`) simple. Ask: “What would break if I added a new optional field to RawJobRow?”

- **Scaling (500k+ rows)**  
  Kaggle DE uses **chunked CSV read** and **batched yield**; dlt writes in chunks. Load script uses one BQ load job over many Parquet files. Ask: “Where would memory or API rate limits bite if we 10x the dataset?”

- **Cost**  
  Taxonomy is free (regex); LLM (Gemini) is only in the compare script unless you add it to ingestion. Parquet in GCS + BQ storage and query cost money. Ask: “What’s the cheapest way to get skills: taxonomy at ingest vs. LLM later in a separate job?”

- **Observability**  
  Logging is in each layer (run_ingestion, pipeline, source, load script). For production you’d add metrics (rows read/written, failures) and alerting. Ask: “How would I know if the last run only wrote half the expected rows?”

- **Testing the flow**  
  Run one source end-to-end (e.g. `kaggle_data_engineer`), then inspect:  
  - GCS: `gsutil ls gs://<bucket>/raw/kaggle_data_engineer_2023/`  
  - BQ: `SELECT COUNT(*), MIN(ingested_at), MAX(ingested_at) FROM ... raw_kaggle_data_engineer_2023`.  
  Then run compare script (taxonomy-only with `--skip-llm` first) to validate skills.

---

## 8. Quick Troubleshooting

| Symptom | Likely cause | What to check |
|---------|----------------|---------------|
| “GCS_BUCKET is required” | Env not set | `export GCS_BUCKET=...` or set in `.env`. |
| Kaggle download fails | Auth | `~/.kaggle/kaggle.json` or `KAGGLE_USERNAME` + `KAGGLE_KEY`. |
| No Parquet in GCS after run_ingestion | Step 1 failed or wrong bucket | Logs from `run_ingestion.py`; `DESTINATION__FILESYSTEM__BUCKET_URL` in pipeline. |
| load_gcs_to_bigquery: “No Parquet files” | Step 1 not run or path mismatch | GCS prefix must match: `raw/kaggle_data_engineer_2023/` (see SOURCE_TO_GCS_AND_TABLE). |
| BQ permission denied | ADC or project | `gcloud auth application-default login`; `GOOGLE_CLOUD_PROJECT` set. |
| compare_skills_extraction LLM empty | No API key or --skip-llm | Set `GOOGLE_API_KEY`; run without `--skip-llm`. |
| skills column empty in BQ | Taxonomy not enabled at ingest | Set `EXTRACT_SKILLS_TAXONOMY=1` and re-run **Step 1** then **Step 2**. |

---

## 9. Where to Go Next

- **RUN_SCRIPTS.md** — Exact commands and options for each script.
- **EVALUATE_SKILLS_EXTRACTION.md** — How to interpret comparison metrics and choose taxonomy vs LLM.
- **DLT_LEARNING_GUIDE.md** — Deep dive on dlt (if present).
- **terraform/README.md** — How the bucket and dataset are created (IaC).

Once you can run one source end-to-end and reason about idempotency, schema, and cost, you’re applying staff-level data engineering thinking to this codebase. Use this guide as the map; the code is the territory.
