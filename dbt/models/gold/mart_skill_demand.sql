-- Gold: skill frequency (from normalized taxonomy/list per job).
{{ config(materialized='view') }}

select
  skill,
  count(*) as job_postings,
  count(distinct source_id) as source_count
from {{ ref('int_skills_long') }}
group by 1
