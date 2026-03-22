-- Silver intermediate: one row per logical posting within each source (latest ingested_at wins).
{{ config(materialized='view') }}

with keyed as (
  select
    *,
    {{ job_dedup_fingerprint() }} as _dedup_fingerprint
  from {{ ref('int_jobs_standardized') }}
),

ranked as (
  select
    *,
    row_number() over (
      partition by source_id, _dedup_fingerprint
      order by ingested_at desc nulls last, job_url nulls last
    ) as _dedup_rank
  from keyed
)

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
  salary_info,
  ingested_at,
  skills_raw,
  _dedup_fingerprint
from ranked
where _dedup_rank = 1
