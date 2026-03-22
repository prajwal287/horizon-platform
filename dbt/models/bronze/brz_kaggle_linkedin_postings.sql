{{ config(materialized='view') }}

select *
from {{ source('lakehouse_raw', 'raw_kaggle_linkedin_postings') }}
