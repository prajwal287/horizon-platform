"""Hugging Face lukebarousse/data_jobs: load, filter (last 3 years, data domain), yield batches."""
import logging
from datetime import date, datetime
from typing import Any, Iterator, List

from datasets import load_dataset

from ingestion.config import CUTOFF_DATE
from ingestion.filters import data_domain_only, last_3_years
from ingestion.schema import RawJobRow

logger = logging.getLogger(__name__)

SOURCE_ID = "huggingface_data_jobs"
SOURCE_NAME = "Hugging Face data_jobs"
BATCH_SIZE = 10_000


def _parse_date(value: Any) -> date | None:
    """Parse posted date from HF dataset (may be datetime or str)."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None
    return None


def _skills_list(value: Any) -> List[str] | None:
    """Normalize job_skills to list of strings."""
    if value is None:
        return None
    if isinstance(value, list):
        return [str(s) for s in value]
    if isinstance(value, str):
        return [value]
    return None


def _row_to_canonical(row: dict[str, Any]) -> RawJobRow | None:
    """Map HF row to canonical schema; return None if filtered out."""
    posted = _parse_date(row.get("job_posted_date"))
    if not last_3_years(posted):
        return None
    title = row.get("job_title")
    desc = None  # HF data_jobs may not have raw description in same row
    skills = _skills_list(row.get("job_skills"))
    job_title_short = row.get("job_title_short")
    if not data_domain_only(
        title=title,
        description=desc,
        skills=skills,
        job_title_short=job_title_short,
    ):
        return None
    return RawJobRow(
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        job_title=title,
        job_description=desc,
        company_name=row.get("company_name"),
        location=row.get("job_location"),
        posted_date=posted,
        job_url=None,
        skills=skills,
        salary_info=str(row.get("salary_year_avg")) if row.get("salary_year_avg") is not None else None,
        ingested_at=datetime.now(),
    )


def stream_huggingface_data_jobs(
    batch_size: int = BATCH_SIZE,
    split: str = "train",
) -> Iterator[List[dict[str, Any]]]:
    """
    Load lukebarousse/data_jobs, filter (last 3 years, data domain), yield batches of load dicts.
    """
    logger.info("Loading Hugging Face dataset lukebarousse/data_jobs (split=%s)", split)
    ds = load_dataset("lukebarousse/data_jobs", split=split, trust_remote_code=True)
    count = 0
    batch: List[dict[str, Any]] = []
    for i, row in enumerate(ds):
        if isinstance(row, dict):
            item = row
        else:
            item = row if hasattr(row, "keys") else dict(row)
        canonical = _row_to_canonical(item)
        if canonical is None:
            continue
        batch.append(canonical.to_load_dict())
        count += 1
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch
    logger.info("Hugging Face data_jobs: yielded %d rows after filters", count)
