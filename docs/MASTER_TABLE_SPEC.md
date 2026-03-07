# Master Table: Columns, Adding Skills, and Clean Data

This doc defines the **final master table columns**, how to **add skills** to Kaggle Data Engineer, how to keep **data types and column names consistent**, and how to build a **master with minimal missing data**.

---

## 1. Adding skills to raw_kaggle_data_engineer_2023

Skills are filled only when ingestion runs with **taxonomy extraction** enabled. To add them:

**Step 1 – Re-run ingestion with taxonomy**

```bash
export EXTRACT_SKILLS_TAXONOMY=1
python3 run_ingestion.py --source kaggle_data_engineer
```

**Step 2 – Re-load that source into BigQuery**

```bash
python3 scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer
```

After this, `raw_kaggle_data_engineer_2023` will have the `skills` column populated (list of canonical skill names from the taxonomy). No code change needed; only re-run with the env var set.

---

## 2. Final master table columns (consistent across all sources)

All raw tables and the master use the **same logical schema**. Below is the canonical list with **BigQuery types** and nullability.

| Column         | BigQuery type   | Nullable | Description |
|----------------|-----------------|----------|-------------|
| source_id      | STRING          | No       | Source identifier (e.g. `kaggle_data_engineer_2023`, `huggingface_data_jobs`, `jobven_jobs`). |
| source_name    | STRING          | No       | Human-readable source name. |
| job_title      | STRING          | Yes      | Job title. |
| job_description| STRING          | Yes      | Job description text. |
| company_name   | STRING          | Yes      | Company name. |
| location       | STRING          | Yes      | Location (city, region, or full string). |
| posted_date    | DATE            | Yes      | Date the job was posted. |
| job_url        | STRING          | Yes      | URL to the job posting. |
| skills         | STRING (JSON) or ARRAY&lt;STRING&gt; | Yes | Skills: store as JSON string `["Python","SQL"]` or as BigQuery ARRAY&lt;STRING&gt;. |
| salary_info    | STRING          | Yes      | Raw salary text (e.g. "100k", "50-60k USD"). |
| ingested_at    | TIMESTAMP       | No       | When the row was ingested. |

**Notes:**

- **skills**: In raw Parquet/BigQuery it may land as JSON string. For a clean master you can keep it as STRING (JSON) or normalize to `ARRAY<STRING>` in a view (see clean view below).
- **posted_date**: Use `DATE`; if a source has only timestamp, cast to `DATE`.
- **ingested_at**: Use `TIMESTAMP` (with timezone if needed).

This is the **single set of columns** for the master; all datasets are mapped to these names and types.

---

## 3. Keeping datatypes and column names consistent

- **Column names**: Already consistent. Every pipeline writes the same fields (see `ingestion/schema.py` and `JOBS_COLUMNS`). Raw tables have the same column names.
- **Datatypes**: BigQuery may infer slightly different types from Parquet (e.g. skills as JSON vs STRING). To enforce consistency, use a **clean master view** that explicitly casts every column (see Section 5 and `scripts/sql/master_jobs_clean_view.sql`). That view is the contract for “same datatype and column name across all datasets.”

---

## 4. Master with very little missing data

Two approaches:

**Option A – Single master view with quality flag**  
Build a view that:
- Unions all raw tables with **consistent types** (CAST each column).
- Adds a **data quality** column, e.g. `is_complete` (TRUE when `job_title` and at least one of `job_description` or `skills` are non-empty).  
You can then query `WHERE is_complete = TRUE` for “master with very less missing data.”

**Option B – Two objects**  
- **master_jobs**: Union of all raw data, same columns, consistent types (may have many nulls).  
- **master_jobs_clean**: Same columns but only rows that meet a minimum completeness rule (e.g. non-empty `job_title` and at least one of `job_description` or `skills`). Use this as the “final master with very less missing data.”

The **final master table columns** are the same in both cases; only the row set (and optional quality column) differs.

---

## 5. Clean master view (consistent types + optional filter)

Use **`scripts/create_master_table.py --clean`** to create a view that:

- Unions all **existing** raw tables (only tables present in your dataset).
- Casts every column to the **final master table types** above.
- Adds `is_complete` for filtering rows with minimal missing data.

```bash
python3 scripts/create_master_table.py --clean
```

The script builds the SQL from the raw tables that exist; no need to run a SQL file manually. Reference SQL is in `scripts/sql/master_jobs_clean_view.sql`.

Then you can point reporting or dbt at this view as the **final master** with consistent columns and fewer missing values if you use the filter.

---

## 6. Summary

| Goal | Action |
|------|--------|
| Add skills to raw_kaggle_data_engineer_2023 | Set `EXTRACT_SKILLS_TAXONOMY=1`, re-run ingestion and load for `kaggle_data_engineer`. |
| Same column names | Already done; all raw tables use the schema in Section 2. |
| Same datatypes | Use the clean master view that CASTs each column to the types in Section 2. |
| Final master columns | Use the 11 columns in Section 2. |
| Master with very less missing data | Use the clean view and filter with `WHERE is_complete = TRUE` or use `master_jobs_clean` (only rows passing completeness rule). |
