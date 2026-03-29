-- Gold: posting counts by source and month (pipeline health / trends).
-- Partition by month + cluster by source_id for dashboard-style time-series by source.
{{ config(
    materialized='table',
    partition_by={'field': 'posting_month', 'data_type': 'date', 'granularity': 'month'},
    cluster_by=['source_id'],
) }}

select
  source_id,
  date_trunc(posted_date, month) as posting_month,
  count(*) as job_postings,
  countif(
    coalesce(trim(job_title), '') != ''
    and (
      coalesce(trim(job_description), '') != ''
      or array_length(skills_normalized) > 0
    )
  ) as complete_postings
from {{ ref('int_jobs_deduplicated') }}
where posted_date is not null
group by 1, 2
