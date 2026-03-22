-- Silver intermediate: trim text, normalize skills to ARRAY<STRING>, derive URL key for matching.
{{ config(materialized='view') }}

select
  source_id,
  source_name,
  nullif(trim(job_title), '') as job_title,
  nullif(trim(job_description), '') as job_description,
  nullif(trim(company_name), '') as company_name,
  nullif(trim(location), '') as location,
  posted_date,
  nullif(trim(job_url), '') as job_url,
  lower(nullif(trim(job_url), '')) as job_url_normalized,
  {{ normalize_skills_array('skills') }} as skills_normalized,
  salary_info,
  ingested_at,
  skills as skills_raw
from {{ ref('stg_jobs_all_sources') }}
