-- Silver intermediate: one row per (job, skill) for aggregations / gold skill mart.
{{ config(materialized='view') }}

select
  source_id,
  source_name,
  job_title,
  company_name,
  posted_date,
  job_url,
  ingested_at,
  trim(skill) as skill
from {{ ref('int_jobs_deduplicated') }},
unnest(skills_normalized) as skill
where array_length(skills_normalized) > 0
  and trim(skill) is not null
  and trim(skill) != ''
