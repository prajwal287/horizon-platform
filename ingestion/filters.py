"""Date and domain filters for last-3-years data-domain-only rows."""
from datetime import date
from typing import List, Optional

from ingestion.config import CUTOFF_DATE, DATA_DOMAIN_JOB_TITLES, DATA_DOMAIN_KEYWORDS


def last_3_years(posted_date: Optional[date]) -> bool:
    """True if posted_date is on or after CUTOFF_DATE. Missing date -> False (drop)."""
    if posted_date is None:
        return False
    return posted_date >= CUTOFF_DATE


def _combined_text(title: Optional[str], description: Optional[str], skills: Optional[List[str]]) -> str:
    """Single searchable string from title, description, skills."""
    parts: List[str] = []
    if title:
        parts.append(title)
    if description:
        parts.append(description)
    if skills:
        parts.append(" ".join(skills) if isinstance(skills, list) else str(skills))
    return " ".join(parts).lower()


def data_domain_only(
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    skills: Optional[List[str]] = None,
    job_title_short: Optional[str] = None,
) -> bool:
    """
    True if the row is in the data domain (title/description/skills or job_title_short).
    Uses job_title_short when present (e.g. Hugging Face), else keyword match.
    """
    if job_title_short and job_title_short.strip():
        if job_title_short.strip() in DATA_DOMAIN_JOB_TITLES:
            return True
    text = _combined_text(title, description, skills)
    if not text:
        return False
    for kw in DATA_DOMAIN_KEYWORDS:
        if kw.lower() in text:
            return True
    return False
