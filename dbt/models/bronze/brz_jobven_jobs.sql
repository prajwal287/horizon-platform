{{ config(materialized='view') }}

select *
from {{ source('lakehouse_raw', 'raw_jobven_jobs') }}
