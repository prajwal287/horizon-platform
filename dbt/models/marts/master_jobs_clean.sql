-- Union of all raw job tables + is_complete (same logic as scripts/sql/master_jobs_clean_view.sql).
-- Materialized as a view in dataset dbt_marts (see dbt_project.yml).

{{ config(materialized='view') }}

WITH raw_union AS (
  SELECT
    CAST(source_id AS STRING)       AS source_id,
    CAST(source_name AS STRING)     AS source_name,
    CAST(job_title AS STRING)       AS job_title,
    CAST(job_description AS STRING) AS job_description,
    CAST(company_name AS STRING)    AS company_name,
    CAST(location AS STRING)        AS location,
    CAST(posted_date AS DATE)       AS posted_date,
    CAST(job_url AS STRING)         AS job_url,
    skills,
    CAST(COALESCE(salary_info, '') AS STRING) AS salary_info,
    CAST(ingested_at AS TIMESTAMP)  AS ingested_at
  FROM {{ source('lakehouse_raw', 'raw_huggingface_data_jobs') }}
  UNION ALL
  SELECT
    CAST(source_id AS STRING),
    CAST(source_name AS STRING),
    CAST(job_title AS STRING),
    CAST(job_description AS STRING),
    CAST(company_name AS STRING),
    CAST(location AS STRING),
    CAST(posted_date AS DATE),
    CAST(job_url AS STRING),
    skills,
    CAST(COALESCE(salary_info, '') AS STRING),
    CAST(ingested_at AS TIMESTAMP)
  FROM {{ source('lakehouse_raw', 'raw_kaggle_data_engineer_2023') }}
  UNION ALL
  SELECT
    CAST(source_id AS STRING),
    CAST(source_name AS STRING),
    CAST(job_title AS STRING),
    CAST(job_description AS STRING),
    CAST(company_name AS STRING),
    CAST(location AS STRING),
    CAST(posted_date AS DATE),
    CAST(job_url AS STRING),
    skills,
    CAST(COALESCE(salary_info, '') AS STRING),
    CAST(ingested_at AS TIMESTAMP)
  FROM {{ source('lakehouse_raw', 'raw_kaggle_linkedin_postings') }}
  UNION ALL
  SELECT
    CAST(source_id AS STRING),
    CAST(source_name AS STRING),
    CAST(job_title AS STRING),
    CAST(job_description AS STRING),
    CAST(company_name AS STRING),
    CAST(location AS STRING),
    CAST(posted_date AS DATE),
    CAST(job_url AS STRING),
    skills,
    CAST(COALESCE(salary_info, '') AS STRING),
    CAST(ingested_at AS TIMESTAMP)
  FROM {{ source('lakehouse_raw', 'raw_kaggle_linkedin_jobs_skills_2024') }}
  UNION ALL
  SELECT
    CAST(source_id AS STRING),
    CAST(source_name AS STRING),
    CAST(job_title AS STRING),
    CAST(job_description AS STRING),
    CAST(company_name AS STRING),
    CAST(location AS STRING),
    CAST(posted_date AS DATE),
    CAST(job_url AS STRING),
    skills,
    CAST(COALESCE(salary_info, '') AS STRING),
    CAST(ingested_at AS TIMESTAMP)
  FROM {{ source('lakehouse_raw', 'raw_jobven_jobs') }}
)
SELECT
  *,
  (
    TRIM(COALESCE(job_title, '')) != ''
    AND (
      TRIM(COALESCE(job_description, '')) != ''
      OR skills IS NOT NULL
    )
  ) AS is_complete
FROM raw_union
