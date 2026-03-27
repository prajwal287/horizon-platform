{{ config(materialized='view', enabled=horizon_raw_table_exists('raw_kaggle_data_engineer_2023')) }}

select *
from {{ source('lakehouse_raw', 'raw_kaggle_data_engineer_2023') }}
