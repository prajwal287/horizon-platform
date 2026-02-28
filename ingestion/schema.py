"""Canonical raw job schema for Silver/Gold consistency across sources."""
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# dlt column spec for the jobs table (used by all pipelines)
JOBS_COLUMNS = {
    "source_id": {"data_type": "text"},
    "source_name": {"data_type": "text"},
    "job_title": {"data_type": "text"},
    "job_description": {"data_type": "text"},
    "company_name": {"data_type": "text"},
    "location": {"data_type": "text"},
    "posted_date": {"data_type": "date"},
    "job_url": {"data_type": "text"},
    "skills": {"data_type": "json"},
    "salary_info": {"data_type": "text"},
    "ingested_at": {"data_type": "timestamp"},
}


class RawJobRow(BaseModel):
    """Canonical raw job posting row; all sources map into this."""

    source_id: str = Field(..., description="Source identifier (e.g. huggingface_data_jobs)")
    source_name: str = Field(..., description="Human-readable source name")
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    posted_date: Optional[date] = None
    job_url: Optional[str] = None
    skills: Optional[List[str]] = None
    salary_info: Optional[str] = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now())

    def to_load_dict(self) -> dict[str, Any]:
        """Dict suitable for dlt load (serialize dates/datetimes)."""
        return self.model_dump(mode="json")
