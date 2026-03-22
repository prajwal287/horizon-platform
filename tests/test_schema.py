"""Contract tests for canonical job schema."""
from datetime import date

import pytest
from ingestion.schema import JOBS_COLUMNS, RawJobRow
from pydantic import ValidationError


def test_jobs_columns_has_required_keys() -> None:
    keys = {
        "source_id",
        "source_name",
        "job_title",
        "job_description",
        "company_name",
        "location",
        "posted_date",
        "job_url",
        "skills",
        "salary_info",
        "ingested_at",
    }
    assert set(JOBS_COLUMNS) == keys


def test_raw_job_row_roundtrip_json() -> None:
    row = RawJobRow(
        source_id="test_source",
        source_name="Test",
        job_title="Data Engineer",
        posted_date=date(2024, 1, 15),
        skills=["Python", "SQL"],
    )
    d = row.to_load_dict()
    assert d["source_id"] == "test_source"
    assert d["job_title"] == "Data Engineer"
    assert d["skills"] == ["Python", "SQL"]
    assert "ingested_at" in d


def test_raw_job_row_requires_source_fields() -> None:
    with pytest.raises(ValidationError):
        RawJobRow(source_id="x")  # type: ignore[call-arg]
