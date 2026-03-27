-- Silver staging: union bronze pass-throughs for raw tables that exist (optional sources).
{{ config(materialized='view') }}

{%- set branches = [] -%}
{%- if horizon_raw_table_exists('raw_huggingface_data_jobs') -%}
  {%- do branches.append("select * from " ~ ref('brz_huggingface_data_jobs')) -%}
{%- endif -%}
{%- if horizon_raw_table_exists('raw_kaggle_data_engineer_2023') -%}
  {%- do branches.append("select * from " ~ ref('brz_kaggle_data_engineer_2023')) -%}
{%- endif -%}
{%- if horizon_raw_table_exists('raw_kaggle_linkedin_postings') -%}
  {%- do branches.append("select * from " ~ ref('brz_kaggle_linkedin_postings')) -%}
{%- endif -%}
{%- if horizon_raw_table_exists('raw_kaggle_linkedin_jobs_skills_2024') -%}
  {%- do branches.append("select * from " ~ ref('brz_kaggle_linkedin_jobs_skills_2024')) -%}
{%- endif -%}

{%- if branches | length == 0 -%}
  {{ exceptions.raise_compiler_error(
    "raw_tables_present has no tables that exist in your project (or list is empty). "
    ~ "From repo root: python scripts/dbt_raw_tables_vars.py — then dbt run --vars \"$(python scripts/dbt_raw_tables_vars.py --json)\" "
    ~ "or edit raw_tables_present in dbt_project.yml to match tables in "
    ~ target.project ~ "." ~ var('bigquery_dataset') ~ "."
  ) }}
{%- endif -%}

{{ branches | join('\nunion all\n') }}
