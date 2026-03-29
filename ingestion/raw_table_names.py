"""Canonical raw BigQuery table names (landing). Order matches preferred union order for master_jobs."""
from __future__ import annotations

RAW_TABLE_IDS: tuple[str, ...] = (
    "raw_huggingface_data_jobs",
    "raw_kaggle_data_engineer_2023",
    "raw_kaggle_linkedin_postings",
    "raw_kaggle_linkedin_jobs_skills_2024",
)
