# How to Execute the Plan Scripts

Run all commands from the **project root**: `horizon-platform/`

**New here?** Read **[END_TO_END_EXECUTION_AND_LEARNING.md](END_TO_END_EXECUTION_AND_LEARNING.md)** first: it explains where execution starts, how data flows (dlt → GCS → BigQuery), and how each script fits in. Use it to build mental models and debug failures.

**Running from scratch?** Use **[RUN_FROM_SCRATCH.md](RUN_FROM_SCRATCH.md)** for a step-by-step walkthrough of Terraform & GCP (variables, outputs, how connections work), then DLT (how we use it, how it connects to GCS). No jargon overload—one concept at a time.

**Minimal path to data in BigQuery:**
1. Set `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT`; for Kaggle add `KAGGLE_USERNAME` + `KAGGLE_KEY`.
2. `python run_ingestion.py --source kaggle_data_engineer`
3. `python scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer`

---

## Load data from scratch (empty GCS and BigQuery)

Use this when you have **no data** in your GCS bucket or BigQuery yet and want to load **all sources** (Hugging Face + all Kaggle streams).

**Step 1 – Set environment variables**

```bash
# Required for ingestion and load (from Terraform outputs or .env)
export GCS_BUCKET=your-bucket-name
export GOOGLE_CLOUD_PROJECT=your-project-id
export BIGQUERY_DATASET=job_market_analysis

# Required for Kaggle sources (all 3 Kaggle pipelines need this)
export KAGGLE_USERNAME=your_kaggle_username
export KAGGLE_KEY=your_kaggle_api_key
```

Ensure GCP auth: `gcloud auth application-default login`.

**Step 2 – Ingest all sources to GCS (Parquet)**

This runs all four pipelines: Hugging Face + Kaggle Data Engineer + Kaggle LinkedIn + Kaggle LinkedIn Skills.

```bash
python3 run_ingestion.py --source all
```

**Step 3 – Load all Parquet from GCS into BigQuery**

Creates or replaces raw tables: `raw_huggingface_data_jobs`, `raw_kaggle_data_engineer_2023`, `raw_kaggle_linkedin_postings`, `raw_kaggle_linkedin_jobs_skills_2024`.

```bash
python3 scripts/load_gcs_to_bigquery.py --source all
```

**Step 4 (optional) – Master table in BigQuery**

Create the unified `master_jobs` view (or table) in BigQuery. Requires `GOOGLE_CLOUD_PROJECT` (or `GCP_PROJECT`) and `BIGQUERY_DATASET`.

```bash
# View (default): simple union of all raw tables
python3 scripts/create_master_table.py

# View with consistent types + is_complete (recommended for analytics)
python3 scripts/create_master_table.py --clean

# Materialized table (faster queries; run once to create, then refresh)
python3 scripts/create_master_table.py --create-table
python3 scripts/create_master_table.py --materialize

# Materialized clean table (consistent types + is_complete)
python3 scripts/create_master_table.py --clean --create-table
python3 scripts/create_master_table.py --clean --materialize
```

**Summary:** `run_ingestion.py --source all` → `load_gcs_to_bigquery.py --source all` → (optional) `create_master_table.py`. To run only one source, use `--source huggingface`, `--source kaggle_data_engineer`, etc., for both commands.

---

## Add skills to raw_kaggle_data_engineer_2023 (from job description)

Skills for the Kaggle Data Engineer 2023 dataset are **extracted from the job description** (and job title) during ingestion using a curated taxonomy (Python, SQL, Spark, AWS, etc.). To populate the `skills` column:

**Step 1 – Re-run ingestion with skills extraction enabled**

From project root:

```bash
export EXTRACT_SKILLS_TAXONOMY=1
python3 run_ingestion.py --source kaggle_data_engineer
```

This reads the CSV, maps `Job_details.1` → job description, and runs taxonomy-based extraction on each row so Parquet in GCS includes a `skills` array.

**Step 2 – Re-load that source into BigQuery**

```bash
python3 scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer
```

After this, `raw_kaggle_data_engineer_2023` in BigQuery will have the `skills` column filled. No code changes are required; only the env var and re-run.

---

## When to use dbt for transformations

Right now, transformations are done in SQL under `scripts/sql/` and by `create_master_table.py`. For when to introduce **dbt** (Silver/Gold layers, tests, incremental models, team workflow), see **[WHEN_TO_USE_DBT.md](WHEN_TO_USE_DBT.md)**.

---

## Prerequisites

1. **Python 3.9+** and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   This installs `kaggle`, `google-generativeai`, `pandas`, etc.  
   **Note:** The codebase uses `Optional[...]` type hints (not `X | None`) for Python 3.9 compatibility. If you see `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`, ensure you are running Python 3.9+ and have the latest code (ingestion uses `typing.Optional`).

2. **For compare script (CSV mode):**  
   - If the dataset is **already** under `data/kaggle/lukkardata-data-engineer-job-postings-2023/` (e.g. from a previous ingestion run), the script uses it and **no Kaggle auth is needed**.  
   - If not, the script will download via the Kaggle API. Set up auth **one** of these ways:  
     - **Option A:** From [Kaggle → Account → Create New API Token](https://www.kaggle.com/settings), download `kaggle.json`, then:
       ```bash
       mkdir -p ~/.kaggle
       mv ~/Downloads/kaggle.json ~/.kaggle/
       chmod 600 ~/.kaggle/kaggle.json
       ```
     - **Option B:** Environment variables (use the same username and key as in `kaggle.json`):
       ```bash
       export KAGGLE_USERNAME=your_kaggle_username
       export KAGGLE_KEY=your_api_key_from_kaggle
       ```
       The Kaggle library expects `KAGGLE_KEY` (not `KAGGLE_API_TOKEN`).

3. **For LLM extraction:** Set a Gemini/Google AI API key:
   ```bash
   export GOOGLE_API_KEY=your_key
   ```
   Get a key at [Google AI Studio](https://aistudio.google.com/apikey).  
   Use the **Google AI** (Generative Language) key from AI Studio, not a GCP project API key. If you see `API_KEY_INVALID`, create a new key at the link above and use it.  
   To run **without** calling Gemini (taxonomy only), use `--skip-llm` and no key is needed.

4. **For BigQuery (compare --from-bigquery or create_master_table):** Set GCP project and ensure Application Default Credentials:
   ```bash
   export GOOGLE_CLOUD_PROJECT=your-project-id
   export BIGQUERY_DATASET=job_market_analysis
   gcloud auth application-default login
   ```

---

## 1. Compare skills extraction (taxonomy vs LLM)

**Script:** `scripts/compare_skills_extraction.py`

### Option A – From Kaggle CSV (downloads dataset if needed)

```bash
# Required: Kaggle credentials (for CSV download)
export KAGGLE_USERNAME=your_kaggle_username
export KAGGLE_API_TOKEN=your_kaggle_api_token   # or KAGGLE_KEY

# Required for LLM extraction (Gemini)
export GOOGLE_API_KEY=your_google_ai_api_key    # or GEMINI_API_KEY

# Run (small sample for a quick test)
python3 scripts/compare_skills_extraction.py --sample 50 --output comparison_skills.csv --print-metrics

# Taxonomy only (no Gemini key needed, no API calls):
python3 scripts/compare_skills_extraction.py --sample 50 --output comparison_skills.csv --print-metrics --skip-llm
```

### Option B – From BigQuery (after raw tables are loaded)

```bash
# Required: GCP project and dataset
export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
export BIGQUERY_DATASET=job_market_analysis

# Optional: for LLM extraction
export GOOGLE_API_KEY=your_google_ai_api_key

# Run
python3 scripts/compare_skills_extraction.py --from-bigquery --sample 100 --output comparison_skills.csv --print-metrics
```

### Arguments

| Argument | Description | Default |
|----------|-------------|--------|
| `--sample` | Max rows to compare | 300 |
| `--output` | Output CSV path | comparison_skills.csv |
| `--from-bigquery` | Read from `raw_kaggle_data_engineer_2023` | off (use CSV) |
| `--print-metrics` | Print summary metrics after writing | off |
| `--llm-batch-size` | Batch size for Gemini calls | 10 |
| `--skip-llm` | Skip LLM extraction (taxonomy only; no API key) | off |

---

## 2. Create master table (BigQuery view or table)

**Script:** `scripts/create_master_table.py`

Run **after** `scripts/load_gcs_to_bigquery.py` has loaded the raw tables.

```bash
export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
export BIGQUERY_DATASET=job_market_analysis

# Create or update the view (default)
python3 scripts/create_master_table.py

# Or create a materialized table (table must exist first)
python3 scripts/create_master_table.py --create-table   # create empty table once
python3 scripts/create_master_table.py --materialize    # truncate and insert
```

---

## 3. Ingest with taxonomy skills (Kaggle DE)

To populate the `skills` column for Kaggle Data Engineer using the taxonomy extractor:

```bash
export GCS_BUCKET=your-bucket
export GOOGLE_CLOUD_PROJECT=your-project
export EXTRACT_SKILLS_TAXONOMY=1

python3 run_ingestion.py --source kaggle_data_engineer
```

Then load to BigQuery:

```bash
python3 scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer
```
