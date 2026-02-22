"""Kaggle lukkardata/data-engineer-job-postings-2023: load, filter, yield batches."""
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, List

import pandas as pd

from ingestion.filters import data_domain_only, last_3_years
from ingestion.schema import RawJobRow
from ingestion.sources.kaggle_download import KAGGLE_BASE, download_dataset

logger = logging.getLogger(__name__)

DATASET = "lukkardata/data-engineer-job-postings-2023"
SOURCE_ID = "kaggle_data_engineer_2023"
SOURCE_NAME = "Kaggle Data Engineer Job Postings 2023"
# No posting date in description; dataset is April 2023
DEFAULT_POSTED_DATE = date(2023, 4, 1)
BATCH_SIZE = 10_000

# Column mapping: normalized key (lowercase, spaces -> underscores) -> canonical field
# Actual CSV may use "Job Title", "Job_title", "Company name", etc.
_NORM_TO_CANON = {
    "job_title": "job_title",
    "title": "job_title",
    "description": "job_description",
    "desc": "job_description",
    "location": "location",
    "company_name": "company_name",
    "company": "company_name",
    "salary": "salary_info",
}


def _norm_col(name: str) -> str:
    """Normalize column name for matching: lowercase, spaces to underscores."""
    s = (name.strip() if isinstance(name, str) else str(name)).lower()
    return s.replace(" ", "_").replace("-", "_")


def _normalize_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map DataFrame column name (as in CSV) -> canonical field name. Flexible matching."""
    out: dict[str, str] = {}
    for c in df.columns:
        n = _norm_col(c)
        if n in _NORM_TO_CANON:
            out[c] = _NORM_TO_CANON[n]
    return out


def _row_to_canonical(row: pd.Series, col_map: dict[str, str]) -> RawJobRow | None:
    posted = DEFAULT_POSTED_DATE
    if not last_3_years(posted):
        return None
    title = None
    desc = None
    for csv_col, canon in col_map.items():
        if canon == "job_title":
            title = row.get(csv_col)
            if pd.notna(title):
                title = str(title).strip() or None
            break
    for csv_col, canon in col_map.items():
        if canon == "job_description":
            desc = row.get(csv_col)
            if pd.notna(desc):
                desc = str(desc).strip() or None
            break
    skills: List[str] | None = None
    # This dataset is 100% Data Engineer postings; if we have no title/desc (column mismatch), still include row
    is_data_domain = data_domain_only(title=title, description=desc, skills=skills)
    if not is_data_domain and (title is None and desc is None):
        is_data_domain = True  # dataset is data-engineer-job-postings-2023
    if not is_data_domain:
        return None
    company = None
    location = None
    salary_info = None
    for csv_col, canon in col_map.items():
        v = row.get(csv_col)
        if pd.isna(v):
            continue
        if canon == "company_name":
            company = str(v).strip()
        elif canon == "location":
            location = str(v).strip()
        elif canon == "salary_info":
            salary_info = str(v).strip()
    return RawJobRow(
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        job_title=title,
        job_description=desc,
        company_name=company,
        location=location,
        posted_date=posted,
        job_url=None,
        skills=skills,
        salary_info=salary_info,
        ingested_at=datetime.now(),
    )


def _find_first_csv(directory: Path) -> Path | None:
    for f in directory.rglob("*.csv"):
        return f
    return None


def stream_kaggle_data_engineer_2023(
    batch_size: int = BATCH_SIZE,
    force_download: bool = False,
) -> Iterator[List[dict[str, Any]]]:
    """Download if needed, load CSV, filter (last 3 years, data domain), yield batches."""
    dest = Path(KAGGLE_BASE) / "lukkardata-data-engineer-job-postings-2023"
    if force_download or not dest.exists():
        download_dataset(DATASET)
    csv_path = _find_first_csv(dest)
    if not csv_path:
        raise FileNotFoundError(f"No CSV found under {dest}")
    col_map = None
    count = 0
    batch: List[dict[str, Any]] = []
    for chunk in pd.read_csv(csv_path, chunksize=batch_size, low_memory=False):
        if col_map is None:
            col_map = _normalize_columns(chunk)
            vals = set(col_map.values())
            # Fallback: match by substring so "Job Title", "job_title_clean", etc. map
            for c in chunk.columns:
                if c in col_map:
                    continue
                n = _norm_col(c)
                if "job_title" not in vals and "title" in n:
                    col_map[c], vals = "job_title", vals | {"job_title"}
                elif "job_description" not in vals and ("description" in n or "desc" in n):
                    col_map[c], vals = "job_description", vals | {"job_description"}
                elif "location" not in vals and ("location" in n or "loc" in n):
                    col_map[c], vals = "location", vals | {"location"}
                elif "company_name" not in vals and "company" in n:
                    col_map[c], vals = "company_name", vals | {"company_name"}
                elif "salary_info" not in vals and "salary" in n:
                    col_map[c], vals = "salary_info", vals | {"salary_info"}
        for _, row in chunk.iterrows():
            canonical = _row_to_canonical(row, col_map)
            if canonical is None:
                continue
            batch.append(canonical.to_load_dict())
            count += 1
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch
    logger.info("Kaggle data_engineer_2023: yielded %d rows after filters", count)
