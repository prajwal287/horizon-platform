-- Union of all raw job tables. Single source of truth for create_master_table.py.
-- Placeholders: {project}, {dataset}
SELECT * FROM `{project}.{dataset}.raw_huggingface_data_jobs`
UNION ALL
SELECT * FROM `{project}.{dataset}.raw_kaggle_data_engineer_2023`
UNION ALL
SELECT * FROM `{project}.{dataset}.raw_kaggle_linkedin_postings`
UNION ALL
SELECT * FROM `{project}.{dataset}.raw_kaggle_linkedin_jobs_skills_2024`
