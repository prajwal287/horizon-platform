# Streamlit app — step-by-step testing

This guide walks through **manual end-to-end testing** of the Horizon Streamlit explorer (`streamlit_app/`). It assumes **BigQuery already has data** (raw tables and/or `master_jobs`) and that **dbt Gold** may exist in separate datasets — see [What the app queries](#what-the-app-queries) below.

---

## What the app queries

The Streamlit UI reads **`GOOGLE_CLOUD_PROJECT`** and **`BIGQUERY_DATASET`** (default `job_market_analysis`). It prefers:

1. **`master_jobs`** view/table if it exists (run `scripts/create_master_table.py` after loading raw data).
2. Otherwise a **`raw_*`** table you select (or the only raw table present).

It does **not** automatically point at **dbt** models under `*_dbt_gold` / `*_dbt_silver`. If you want dashboards on Gold tables, extend `streamlit_app/` or run SQL in BigQuery and point a new page at those relations.

---

## Prerequisites checklist

| Step | Verify |
|------|--------|
| 1. GCP auth | `gcloud auth application-default login` |
| 2. Project & dataset in `.env` | `GOOGLE_CLOUD_PROJECT`, `BIGQUERY_DATASET` (and full `GCS_BUCKET` if you also run ingestion) |
| 3. Data in BigQuery | At least one `raw_*` table or `master_jobs` in the dataset |
| 4. Python deps | From repo root: `pip install -r requirements.txt` |
| 5. Optional: Hugging Face | `HF_TOKEN` in `.env` only affects **ingestion**, not Streamlit reads |

---

## A — Quick import smoke test (no browser)

From **repository root** (folder that contains `streamlit_app/`):

```bash
python3 -c "
import sys
from pathlib import Path
root = Path('.').resolve()
sys.path.insert(0, str(root))
from streamlit_app.bq_helpers import get_project_id, get_dataset_id, bq_client
p, d = get_project_id(), get_dataset_id()
assert p, 'Set GOOGLE_CLOUD_PROJECT in .env'
c = bq_client(p)
n = list(c.query(f'SELECT COUNT(*) AS n FROM \`{p}.{d}.INFORMATION_SCHEMA.TABLES\` WHERE STARTS_WITH(table_name, \"raw_\")').result())[0]['n']
print('OK project=', p, 'dataset=', d, 'raw-like tables=', n)
"
```

- If this raises **`AssertionError`**, fix `.env` / exports.
- If **`raw-like tables=0`** and no `master_jobs`, load data first (`load_gcs_to_bigquery.py`, then optional `create_master_table.py`).

---

## B — Run Streamlit locally

1. **Activate your venv** (if you use one):

   ```bash
   cd /path/to/horizon-platform/horizon-platform
   source .venv/bin/activate   # or: python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Start the app** (must run from **repo root** so imports resolve):

   ```bash
   streamlit run streamlit_app/app.py
   ```

3. **Open** the URL shown (default **http://localhost:8501**).

4. **Stop** with `Ctrl+C` in the terminal.

---

## C — Run Streamlit in Docker

From repo root:

```bash
docker compose build
docker compose up streamlit
```

Open **http://localhost:8501**.  
The service uses the same **ADC mount** as the `app` service (`~/.config/gcloud`) and loads `.env` if present.

---

## D — Manual UI test script (checklist)

After the app loads without a red connection error:

| # | Action | Expected |
|---|--------|----------|
| 1 | Sidebar shows **GCP project** and **BigQuery dataset** | Matches your `.env` |
| 2 | **Data source** banner | “Using unified view **master_jobs**” or a **raw_** table warning/selector |
| 3 | **Rows (filtered)** metric | Non-zero count if data exists and filters are not over-restrictive |
| 4 | **By source** tab | Bar chart + table when `master_jobs` has multiple `source_id` values |
| 5 | **Over time** tab | Line chart if `posted_date` is populated |
| 6 | **Browse jobs** tab | Table of jobs; **Download CSV** downloads a file |
| 7 | Sidebar **Search** | Narrows rows when you type a keyword (e.g. `engineer`) |
| 8 | Sidebar **Filter by posted date** | Restricts rows when dates are set |
| 9 | Sidebar **Source** multi-select | Appears with `master_jobs`; subset of sources filters correctly |
| 10 | **About** expander | Text explains `master_jobs` vs raw and pipeline order |

If **“No raw_* tables found”** or BigQuery errors: confirm dataset name, ADC, and that tables exist in the Console.

---

## E — Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| `GOOGLE_CLOUD_PROJECT` empty in UI | Set in `.env` or export before `streamlit run` |
| `403` / `Access Denied` | IAM on BigQuery; ADC account needs jobs + table read on the dataset |
| Empty charts | Filters too tight; clear search and date filter |
| Import error `streamlit_app` | Run from **repo root**, not from inside `streamlit_app/` |
| Docker: blank auth | Run `gcloud auth application-default login` on the **host**; container mounts that JSON |

---

## F — After dbt Gold

- **Data quality / row checks:** use `scripts/data_quality_checks.py` and BigQuery / `dbt test` for Bronze–Silver–Gold.
- **Streamlit:** today’s app is for **exploring landed raw / `master_jobs`**. To “test” Gold metrics in a UI, add a new Streamlit page or query `project.job_market_analysis_dbt_gold.mart_*` in a fork of `bq_helpers.py` (separate follow-up).

---

## G — One-line reference

```bash
# Local
streamlit run streamlit_app/app.py

# Docker
docker compose up streamlit
```

Principal code: `streamlit_app/app.py`, `streamlit_app/bq_helpers.py`.
