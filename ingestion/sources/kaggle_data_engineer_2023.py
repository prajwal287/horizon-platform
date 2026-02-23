"""Kaggle lukkardata/data-engineer-job-postings-2023: load, filter, yield batches."""
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, List

import pandas as pd

from ingestion.filters import last_3_years
from ingestion.schema import RawJobRow
from ingestion.sources.kaggle_download import KAGGLE_BASE, download_dataset

logger = logging.getLogger(__name__)

DATASET = "lukkardata/data-engineer-job-postings-2023"
SOURCE_ID = "kaggle_data_engineer_2023"
SOURCE_NAME = "Kaggle Data Engineer Job Postings 2023"
# No posting date in description; dataset is April 2023
DEFAULT_POSTED_DATE = date(2023, 4, 1)
BATCH_SIZE = 10_000

# Explicit mapping for lukkardata/data-engineer-job-postings-2023 (117-column cleaned format).
# From inspect: Job_details=Title, Job_details.1=Description, Company_info=Name, Job_details.4=City, etc.
_EXACT_COLUMN_MAP: dict[str, str] = {
    "Job_details": "job_title",
    "Job_details.1": "job_description",
    "Company_info": "company_name",
    "Job_details.4": "location_city",
    "Job_details.5": "location_state",
    "Job_details.6": "location_country",
    "Salary.2": "salary_avg",
    "Salary.3": "salary_currency",
}

# Fallback: normalized key -> canonical (for other CSV variants)
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
    """Map DataFrame column name (as in CSV) -> canonical field name. Uses exact map first."""
    out: dict[str, str] = {}
    cols = set(df.columns)
    for csv_col, canon in _EXACT_COLUMN_MAP.items():
        if csv_col in cols:
            out[csv_col] = canon
    if out:
        return out
    for c in df.columns:
        n = _norm_col(c)
        if n in _NORM_TO_CANON:
            out[c] = _NORM_TO_CANON[n]
    return out


def _row_to_canonical(row: pd.Series, col_map: dict[str, str]) -> RawJobRow | None:
    posted = DEFAULT_POSTED_DATE
    if not last_3_years(posted):
        return None
    # This dataset is 100% Data Engineer postings — skip domain filter
    title = None
    desc = None
    company = None
    location_city = None
    location_state = None
    location_country = None
    location_single = None
    salary_avg = None
    salary_currency = None
    for csv_col, canon in col_map.items():
        v = row.get(csv_col)
        if pd.isna(v):
            continue
        s = str(v).strip()
        if not s:
            continue
        if canon == "job_title":
            title = s
        elif canon == "job_description":
            desc = s
        elif canon == "company_name":
            company = s
        elif canon == "location":
            location_single = s
        elif canon == "location_city":
            location_city = s
        elif canon == "location_state":
            location_state = s
        elif canon == "location_country":
            location_country = s
        elif canon == "salary_info":
            salary_avg = s
        elif canon == "salary_avg":
            salary_avg = s
        elif canon == "salary_currency":
            salary_currency = s
    location = location_single or ", ".join(
        filter(None, [location_city, location_state, location_country])
    ) or None
    salary_info = None
    if salary_avg or salary_currency:
        salary_info = " ".join(filter(None, [salary_avg, salary_currency]))
    skills: List[str] | None = None
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


def _find_csvs(directory: Path) -> List[Path]:
    return sorted(directory.rglob("*.csv"), key=lambda p: p.stat().st_size, reverse=True)


def _find_best_csv(directory: Path) -> Path | None:
    """Return the largest CSV (by file size) so we prefer the main data file over small metadata CSVs."""
    csvs = _find_csvs(directory)
    return csvs[0] if csvs else None


def stream_kaggle_data_engineer_2023(
    batch_size: int = BATCH_SIZE,
    force_download: bool = False,
) -> Iterator[List[dict[str, Any]]]:
    """Download if needed, load CSV, filter (last 3 years, data domain), yield batches."""
    dest = Path(KAGGLE_BASE) / "lukkardata-data-engineer-job-postings-2023"
    if force_download or not dest.exists():
        download_dataset(DATASET)
    csv_path = _find_best_csv(dest)
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
            logger.info(
                "Kaggle data_engineer_2023: CSV %s has %d columns, mapped %d (sample: %s)",
                csv_path.name,
                len(chunk.columns),
                len(col_map),
                list(col_map.keys())[:8],
            )
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
