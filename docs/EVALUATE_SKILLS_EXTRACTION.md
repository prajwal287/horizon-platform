# Evaluating Skills Extraction: Taxonomy vs LLM

This doc describes how to run the comparison between taxonomy-based and LLM (Gemini) skills extraction and how to choose which approach to use in production.

## 1. Run the comparison

From project root:

```bash
# Using Kaggle DE CSV (downloads dataset if needed). Requires KAGGLE_USERNAME, KAGGLE_API_TOKEN.
# For LLM you need GOOGLE_API_KEY or GEMINI_API_KEY.
python scripts/compare_skills_extraction.py --sample 300 --output comparison_skills.csv --print-metrics
```

Or read from BigQuery after loading raw tables:

```bash
export GOOGLE_CLOUD_PROJECT=your-project
export BIGQUERY_DATASET=job_market_analysis
python scripts/compare_skills_extraction.py --from-bigquery --sample 200 --output comparison_skills.csv --print-metrics
```

The script writes a CSV with columns: `row_id`, `job_title`, `description_snippet`, `skills_taxonomy`, `skills_llm`, `jaccard_similarity`.

With `--print-metrics` it also prints:

- Mean Jaccard similarity (agreement between taxonomy and LLM)
- % of rows with taxonomy skills non-empty
- % of rows with LLM skills non-empty
- Mean number of skills per row for each method

## 2. Review the output

- Open `comparison_skills.csv` and spot-check rows where `jaccard_similarity` is low or where one method is empty and the other is not.
- Optionally label a subset (e.g. 50–100 rows) with ground-truth skills and compute precision/recall for each method.

## 3. Make the call

Choose one of:

| Choice | When | How |
|--------|------|-----|
| **Taxonomy only** | You want no API cost, deterministic output, and good precision. | Set `EXTRACT_SKILLS_TAXONOMY=1` when running the Kaggle DE pipeline. Skills are filled in ingestion. |
| **LLM only** | You want higher recall and can accept API cost. | Add a post-load enrichment step that calls `extract_skills_llm()` for each row (or batch) and writes to the `skills` column or a silver table. |
| **Hybrid** | You want taxonomy by default and LLM for empty rows. | Use taxonomy in the pipeline (EXTRACT_SKILLS_TAXONOMY=1); add a job that runs LLM for rows where `skills` is null or empty and merges results into a silver view/table. |

After you decide, keep the chosen path and document it; the other paths remain in the codebase for experimentation.

## 4. Enabling taxonomy in the pipeline

To turn on taxonomy-based skills for Kaggle Data Engineer 2023:

```bash
export EXTRACT_SKILLS_TAXONOMY=1
python run_ingestion.py --source kaggle_data_engineer
```

Then run `scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer` as usual.
