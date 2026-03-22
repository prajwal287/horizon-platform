-- Bronze: pass-through from landed raw (audit / lineage boundary).
{{ config(materialized='view') }}

select *
from {{ source('lakehouse_raw', 'raw_huggingface_data_jobs') }}
