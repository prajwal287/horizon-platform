{{ config(materialized='view', enabled=horizon_raw_table_exists('raw_kaggle_linkedin_jobs_skills_2024')) }}

select *
from {{ source('lakehouse_raw', 'raw_kaggle_linkedin_jobs_skills_2024') }}
