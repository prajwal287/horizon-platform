{{ config(materialized='view', enabled=horizon_raw_table_exists('raw_kaggle_linkedin_postings')) }}

select *
from {{ source('lakehouse_raw', 'raw_kaggle_linkedin_postings') }}
