-- Gold: analytics-ready job grain (deduped) + data-quality flag.
{{ config(materialized='view') }}

select
  source_id,
  source_name,
  job_title,
  job_description,
  company_name,
  location,
  posted_date,
  job_url,
  job_url_normalized,
  skills_normalized,
  array_length(skills_normalized) as skill_count,
  salary_info,
  ingested_at,
  (
    coalesce(trim(job_title), '') != ''
    and (
      coalesce(trim(job_description), '') != ''
      or array_length(skills_normalized) > 0
    )
  ) as is_complete,
  (
    case
      when posted_date is null then 'missing_date'
      when coalesce(trim(job_title), '') = '' then 'missing_title'
      when coalesce(trim(job_description), '') = '' and array_length(skills_normalized) = 0 then 'thin_description'
      else 'ok'
    end
  ) as content_quality_bucket
from {{ ref('int_jobs_deduplicated') }}
