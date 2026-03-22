-- Gold: same normalized apply URL appearing in more than one source (overlap / dedup QA).
{{ config(materialized='view') }}

select
  job_url_normalized,
  count(*) as row_count,
  count(distinct source_id) as distinct_sources
from {{ ref('int_jobs_deduplicated') }}
where job_url_normalized is not null
group by job_url_normalized
having count(distinct source_id) > 1
