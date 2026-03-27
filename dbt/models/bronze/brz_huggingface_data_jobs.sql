-- Bronze: pass-through from landed raw (audit / lineage boundary).
{{ config(materialized='view', enabled=horizon_raw_table_exists('raw_huggingface_data_jobs')) }}

select *
from {{ source('lakehouse_raw', 'raw_huggingface_data_jobs') }}
