"""Kaggle asaniczka/1-3m-linkedin-jobs-and-skills-2024: load, filter, yield batches."""
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, List

import pandas as pd

from ingestion.filters import data_domain_only, last_3_years
from ingestion.schema import RawJobRow
from ingestion.sources.kaggle_download import KAGGLE_BASE, download_dataset

logger = logging.getLogger(__name__)

DATASET = "asaniczka/1-3m-linkedin-jobs-and-skills-2024"
SOURCE_ID = "kaggle_linkedin_jobs_skills_2024"
SOURCE_NAME = "Kaggle 1.3M LinkedIn Jobs & Skills 2024"
DEFAULT_POSTED_DATE = date(2024, 1, 1)
BATCH_SIZE = 10_000


def _infer_column_map(df: pd.DataFrame) -> dict[str, str]:
    """Infer CSV column -> canonical from common names."""
    col_map: dict[str, str] = {}
    for c in df.columns:
        s = str(c).lower().strip()
        if "title" in s or "job_title" in s or "job" == s:
            col_map[c] = "job_title"
        elif "description" in s or "desc" in s or "content" in s:
            col_map[c] = "job_description"
        elif "company" in s:
            col_map[c] = "company_name"
        elif "location" in s or "loc" in s or "place" in s:
            col_map[c] = "location"
        elif "salary" in s or "pay" in s:
            col_map[c] = "salary_info"
        elif "posted" in s or "date" in s or "time" in s:
            col_map[c] = "posted_date"
        elif "url" in s or "link" in s:
            col_map[c] = "job_url"
        elif "skill" in s:
            col_map[c] = "skills"
    return col_map


def _parse_date(val: Any) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


def _skills_to_list(val: Any) -> List[str] | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        if ";" in val or "|" in val or "," in val:
            return [x.strip() for x in val.replace(";", "|").replace(",", "|").split("|") if x and x.strip()]
        return [val.strip()] if val.strip() else None
    return None


def _row_to_canonical(row: pd.Series, col_map: dict[str, str]) -> RawJobRow | None:
    posted = DEFAULT_POSTED_DATE
    for csv_col, canon in col_map.items():
        if canon == "posted_date":
            v = _parse_date(row.get(csv_col))
            if v:
                posted = v
            break
    if not last_3_years(posted):
        return None
    title = None
    desc = None
    skills = None
    for csv_col, canon in col_map.items():
        v = row.get(csv_col)
        if pd.isna(v):
            continue
        if canon == "job_title":
            title = str(v).strip() or None
        elif canon == "job_description":
            desc = str(v).strip() or None
        elif canon == "skills":
            skills = _skills_to_list(v)
    if not data_domain_only(title=title, description=desc, skills=skills):
        return None
    company = None
    location = None
    salary_info = None
    job_url = None
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
        elif canon == "job_url":
            job_url = str(v).strip()
    return RawJobRow(
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        job_title=title,
        job_description=desc,
        company_name=company,
        location=location,
        posted_date=posted,
        job_url=job_url,
        skills=skills,
        salary_info=salary_info,
        ingested_at=datetime.now(),
    )


def _find_first_csv(directory: Path) -> Path | None:
    for f in directory.rglob("*.csv"):
        return f
    return None


def stream_kaggle_linkedin_jobs_skills_2024(
    batch_size: int = BATCH_SIZE,
    force_download: bool = False,
) -> Iterator[List[dict[str, Any]]]:
    """Download if needed, load CSV, filter (last 3 years, data domain), yield batches."""
    dest = Path(KAGGLE_BASE) / "asaniczka-1-3m-linkedin-jobs-and-skills-2024"
    if force_download or not dest.exists():
        download_dataset(DATASET)
    csv_path = _find_first_csv(dest)
    if not csv_path:
        raise FileNotFoundError(f"No CSV found under {dest}")
    col_map: dict[str, str] | None = None
    count = 0
    batch: List[dict[str, Any]] = []
    for chunk in pd.read_csv(csv_path, chunksize=batch_size, low_memory=False):
        if col_map is None:
            col_map = _infer_column_map(chunk)
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
    logger.info("Kaggle linkedin_jobs_skills_2024: yielded %d rows after filters", count)
