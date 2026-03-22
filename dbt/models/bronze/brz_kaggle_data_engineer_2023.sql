{{ config(materialized='view') }}

select *
from {{ source('lakehouse_raw', 'raw_kaggle_data_engineer_2023') }}
