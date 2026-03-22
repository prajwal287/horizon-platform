-- Silver staging: single stream of all bronze tables (same canonical columns).
{{ config(materialized='view') }}

select * from {{ ref('brz_huggingface_data_jobs') }}
union all
select * from {{ ref('brz_kaggle_data_engineer_2023') }}
union all
select * from {{ ref('brz_kaggle_linkedin_postings') }}
union all
select * from {{ ref('brz_kaggle_linkedin_jobs_skills_2024') }}
union all
select * from {{ ref('brz_jobven_jobs') }}
