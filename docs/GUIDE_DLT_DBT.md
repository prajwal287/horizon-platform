# dlt and dbt — tutorials and scenarios

**dlt** and **dbt** solve **different** problems in this repo. Together they implement: **batch ingest to a lake → warehouse tables → versioned SQL transformations**.

---

## Why two tools?

| Concern | Tool | In Horizon |
|---------|------|------------|
| **Moving** data from APIs/files into **files** in the lake | **dlt** | Parquet under `gs://…/raw/<dataset_name>/` |
| **Defining** **business-ready** tables in SQL, with tests and lineage | **dbt** | Bronze / silver / gold in BigQuery; key **gold marts** are **partitioned tables** where it helps scans |

dlt is **Python-first** (resources, pipelines, destinations). dbt is **SQL-first** (models, macros, tests).

---

## dlt in this codebase (batch)

1. **Resource** — a stream of dict rows with schema hints (`JOBS_COLUMNS` in `ingestion/schema.py`).
2. **Pipeline** — `dlt.pipeline(..., destination="filesystem", dataset_name=…)` writes **Parquet** to GCS.
3. **Disposition** — `write_disposition="replace"` ⇒ each run replaces that source’s files (full refresh semantics for that slice).
4. **Important path rule** — `DESTINATION__FILESYSTEM__BUCKET_URL` must point at `gs://BUCKET/raw` **without** duplicating `dataset_name`; see `ingestion/pipelines/common.py`.

**Run:** `run_ingestion.py --source …` (or `--source all`).

---

## From GCS to BigQuery (not dlt)

`scripts/load_gcs_to_bigquery.py` lists Parquet under `raw/<slug>/` and loads **`WRITE_TRUNCATE`** into `raw_*`. This keeps the **lake** (cheap, replayable files) separate from the **warehouse table** used for SQL/dbt.

---

## dbt in this codebase (medallion)

After `raw_*` exist:

| Layer | Dataset suffix (typical) | Role |
|-------|--------------------------|------|
| **Bronze** | `_dbt_bronze` | One view per raw table (lineage). |
| **Silver** | `_dbt_silver` | Union, standardize skills, dedupe, skills-long. |
| **Gold** | `_dbt_gold` | `mart_jobs_curated`, volumes, skill demand, URL overlap. |

**BigQuery layout (peer review / cost):** `mart_jobs_curated` is materialized as a **table** **partitioned by month on `posted_date`** and **clustered by `source_id` and `content_quality_bucket`** so filters like “these sources, this date range, this quality bucket” prune partitions/blocks. `mart_posting_volume` is **partitioned on `posting_month`** and **clustered by `source_id`** for monthly trends by provider—the same shapes the Streamlit app charts use. Other gold models stay **views** where they are small aggregates.

**Run:** `cd dbt && dbt run && dbt test`  
Profile: copy `dbt/profiles.yml.example` → `~/.dbt/profiles.yml`.

**Macros:** `dbt/macros/medallion.sql` (`normalize_skills_array`, `job_dedup_fingerprint`).

---

## Scenario A — First full batch (all public sources)

1. Terraform + `.env` with `GCS_BUCKET`, `GOOGLE_CLOUD_PROJECT`, Kaggle creds if needed.  
2. `run_ingestion.py --source all`  
3. `load_gcs_to_bigquery.py --source all`  
4. Optional: `create_master_table.py --clean`  
5. Optional: `dbt run`

**Outcome:** `raw_*`, optional `master_jobs`, optional gold marts.

---

## Scenario B — Hugging Face only (fast check)

1. `run_ingestion.py --source huggingface`  
2. `load_gcs_to_bigquery.py --source huggingface`  
3. Streamlit: pick raw table or build `master_jobs` later.

---

## Scenario C — Refresh one Kaggle source after upstream change

1. `run_ingestion.py --source kaggle_data_engineer`  
2. `load_gcs_to_bigquery.py --source kaggle_data_engineer`  
3. If you use **dbt**, `dbt run` (incremental models are not assumed for `raw_*` overwrite—treat as full refresh for that source’s land pattern).

---

## Scenario D — dbt fails: “table not found”

- **Cause:** `sources.yml` lists a `raw_*` table you never loaded.  
- **Fix:** Load that source, **or** remove/comment that source in `dbt/models/sources.yml`, or use `scripts/dbt_raw_tables_vars.py` to align vars with what exists.

---

## Scenario E — When to add dbt (decision)

- **Only ad-hoc SQL on `raw_*`:** dbt optional.  
- **Deduped job grain + skill analytics + tests in CI:** add **dbt** as implemented here.

---

## Mental model for peers / interviews

> “We use **dlt** to batch-ingest heterogeneous job JSON/CSV into **Parquet on GCS**, then a **deterministic loader** moves Parquet into **BigQuery raw tables**. **dbt** builds medallion models so dashboards and analysts hit **curated marts**, not one-off notebook SQL.”
