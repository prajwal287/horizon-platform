"""Jobven API: fetch US jobs from last 24h (free tier: 10/page, 300 calls/month)."""
import logging
import os
import time
from datetime import date, datetime, timezone, timedelta
from typing import Any, Iterator, List, Optional

import requests

from ingestion.filters import data_domain_only
from ingestion.schema import RawJobRow

logger = logging.getLogger(__name__)

SOURCE_ID = "jobven_jobs"
SOURCE_NAME = "Jobven (last 24h, US)"
# Free tier: max 10 per page, 300 API calls/month
PAGE_LIMIT = 10
MAX_PAGES_DEFAULT = 3  # 30 jobs/run; ~90 calls/month if run daily
BASE_URL = "https://api.jobven.com/v1/public/jobs"
# Query for data-domain jobs (free tier has low page size, so one keyword)
DEFAULT_QUERY = "data engineer"


def _posted_after_24h() -> int:
    """Unix seconds for 24 hours ago (for postedAfter)."""
    return int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())


def _location_str(locations: Optional[List[Any]]) -> Optional[str]:
    """Format locations array to a single string."""
    if not locations or not isinstance(locations, list):
        return None
    parts: List[str] = []
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        city = loc.get("addressLocality")
        region = loc.get("addressRegion")
        country = loc.get("addressCountry")
        work = loc.get("workLocation")
        segs = [s for s in (city, region, country) if s]
        if segs:
            parts.append(", ".join(segs))
        if work and work not in (segs or []):
            parts.append(work)
    return "; ".join(parts) if parts else None


def _skills_list(skills: Optional[dict]) -> Optional[List[str]]:
    """Flatten primary_skills + secondary_skills to one list."""
    if not skills or not isinstance(skills, dict):
        return None
    out: List[str] = []
    for key in ("primary_skills", "secondary_skills"):
        val = skills.get(key)
        if isinstance(val, list):
            out.extend(str(s) for s in val)
    return out if out else None


def _salary_str(salary: Optional[dict]) -> Optional[str]:
    """Format salary object to string."""
    if not salary or not isinstance(salary, dict):
        return None
    mn = salary.get("min")
    mx = salary.get("max")
    currency = salary.get("currency", "")
    period = salary.get("period", "")
    if mn is not None and mx is not None:
        return f"{currency} {mn}-{mx} {period}".strip()
    if mn is not None:
        return f"{currency} {mn}+ {period}".strip()
    return None


def _job_to_canonical(job: dict[str, Any]) -> Optional[RawJobRow]:
    """Map one Jobven job to RawJobRow; return None if not data-domain."""
    title = job.get("title")
    description = job.get("description") or job.get("summary")
    skills = _skills_list(job.get("skills"))
    if not data_domain_only(
        title=title,
        description=description,
        skills=skills,
        job_title_short=None,
    ):
        return None
    companies = job.get("companies")
    company_name = None
    if isinstance(companies, list) and companies:
        first = companies[0]
        if isinstance(first, dict):
            company_name = first.get("name")
    posted_at = job.get("postedAt")
    if isinstance(posted_at, (int, float)):
        try:
            posted_date = date.fromtimestamp(int(posted_at))
        except (ValueError, OSError):
            posted_date = None
    else:
        posted_date = None
    return RawJobRow(
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        job_title=title,
        job_description=description,
        company_name=company_name,
        location=_location_str(job.get("locations")),
        posted_date=posted_date,
        job_url=job.get("applyUrl"),
        skills=skills,
        salary_info=_salary_str(job.get("salary")),
        ingested_at=datetime.now(timezone.utc),
    )


def stream_jobven_jobs(
    api_key: Optional[str] = None,
    query: str = DEFAULT_QUERY,
    country: str = "US",
    posted_after: Optional[int] = None,
    limit: int = PAGE_LIMIT,
    max_pages: int = MAX_PAGES_DEFAULT,
    batch_size: int = 500,
) -> Iterator[List[dict[str, Any]]]:
    """
    Fetch Jobven jobs (last 24h, US, keyword filter), map to canonical rows, yield batches.
    Free tier: use limit=10, max_pages=3 to stay under 300 calls/month if run daily.
    """
    key = (api_key or os.environ.get("JOBVEN_API_KEY", "")).strip()
    if not key:
        logger.warning("JOBVEN_API_KEY not set; skipping Jobven source")
        return
    if posted_after is None:
        posted_after = _posted_after_24h()
    params: dict[str, Any] = {
        "q": query,
        "country": country,
        "postedAfter": posted_after,
        "limit": min(limit, PAGE_LIMIT),
    }
    headers = {"X-API-Key": key}
    total_yielded = 0
    page = 0
    cursor: Optional[str] = None
    batch: List[dict[str, Any]] = []

    while page < max_pages:
        if cursor:
            params["cursor"] = cursor
        try:
            resp = requests.get(
                BASE_URL,
                params=params,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            body = resp.json()
        except requests.RequestException as e:
            logger.exception("Jobven API request failed: %s", e)
            break
        except ValueError as e:
            logger.exception("Jobven API invalid JSON: %s", e)
            break

        data = body.get("data") or []
        meta = body.get("meta") or {}
        for job in data:
            if not isinstance(job, dict):
                continue
            row = _job_to_canonical(job)
            if row is None:
                continue
            batch.append(row.to_load_dict())
            total_yielded += 1
            if len(batch) >= batch_size:
                yield batch
                batch = []

        page += 1
        has_more = meta.get("hasMore") and meta.get("nextCursor")
        if not has_more:
            break
        cursor = meta.get("nextCursor")
        if not cursor:
            break
        # Avoid rate limits
        time.sleep(0.5)

    if batch:
        yield batch
    logger.info("Jobven: yielded %d rows (pages=%d)", total_yielded, page)
