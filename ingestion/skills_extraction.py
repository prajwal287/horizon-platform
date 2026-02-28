"""Skills extraction from job title/description: taxonomy-based and LLM (Gemini)."""
import json
import logging
import os
import re
from typing import Optional

from ingestion.config import (
    DATA_ENGINEER_SKILL_ALIASES,
    DATA_ENGINEER_SKILLS,
)

logger = logging.getLogger(__name__)

# Match whole-word or phrase (word boundary for single words; allow hyphen/underscore in tokens)
def _make_pattern(skill: str) -> re.Pattern[str]:
    escaped = re.escape(skill)
    if " " in skill or "/" in skill:
        return re.compile(rf"\b{escaped}\b", re.IGNORECASE)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


# Precompile patterns for DATA_ENGINEER_SKILLS (longer phrases first)
_SKILL_PATTERNS: list[tuple[re.Pattern[str], str]] = []
for _skill in DATA_ENGINEER_SKILLS:
    canonical = DATA_ENGINEER_SKILL_ALIASES.get(_skill.lower(), _skill.title())
    _SKILL_PATTERNS.append((_make_pattern(_skill), canonical))


def extract_skills_taxonomy(
    title: Optional[str],
    description: Optional[str],
) -> list[str]:
    """
    Extract skills from job title and description using a curated taxonomy.
    Uses whole-word/phrase matching; returns sorted, deduplicated list with canonical names.
    """
    text_parts: list[str] = []
    if title and isinstance(title, str) and title.strip():
        text_parts.append(title.strip())
    if description and isinstance(description, str) and description.strip():
        text_parts.append(description.strip())
    if not text_parts:
        return []
    text = " ".join(text_parts).lower()
    found: set[str] = set()
    for pattern, canonical in _SKILL_PATTERNS:
        if pattern.search(text):
            found.add(canonical)
    return sorted(found)


# Prompt for Gemini: extract technical skills only, return JSON array
_SKILLS_EXTRACT_PROMPT = """Extract only the technical skills and tools mentioned in the following job posting.
Return a JSON array of strings, nothing else. No explanation. Example: ["Python", "SQL", "AWS"].

Job title: {title}

Job description:
{description}"""


def _parse_skills_json(raw: str) -> list[str]:
    """Parse model output into list of skill strings. Tolerates markdown code blocks."""
    s = raw.strip()
    if not s:
        return []
    if s.startswith("```"):
        lines = s.split("\n")
        s = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        out = json.loads(s)
        if isinstance(out, list):
            return [str(x).strip() for x in out if x and str(x).strip()]
        return []
    except json.JSONDecodeError:
        logger.debug("Could not parse skills JSON: %s", raw[:200])
        return []


def extract_skills_llm(
    title: Optional[str],
    description: Optional[str],
    *,
    model_name: str = "gemini-1.5-flash",
    api_key: Optional[str] = None,
) -> list[str]:
    """
    Extract skills from job title and description using Gemini 1.5 Flash.
    Returns a list of skill strings. Requires GOOGLE_API_KEY or GEMINI_API_KEY in env (or api_key arg).
    """
    api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("No API key for Gemini; set GOOGLE_API_KEY or GEMINI_API_KEY. Returning [].")
        return []
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_name)
        title_str = (title or "").strip() or "(not provided)"
        desc_str = (description or "").strip() or "(not provided)"
        prompt = _SKILLS_EXTRACT_PROMPT.format(title=title_str, description=desc_str[:8000])
        response = model.generate_content(prompt)
        if not response or not response.text:
            return []
        return _parse_skills_json(response.text)
    except Exception as e:
        logger.warning("Gemini skills extraction failed: %s", e)
        return []


def extract_skills_llm_batch(
    rows: list[tuple[Optional[str], Optional[str]]],
    *,
    model_name: str = "gemini-1.5-flash",
    api_key: Optional[str] = None,
    batch_size: int = 10,
) -> list[list[str]]:
    """
    Run LLM skills extraction on multiple rows. Each row is (title, description).
    Returns a list of skill lists, one per row. Batches multiple jobs into one prompt to reduce cost.
    """
    api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("No API key for Gemini; set GOOGLE_API_KEY or GEMINI_API_KEY. Returning [] for all.")
        return [[] for _ in rows]
    results: list[list[str]] = []
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        numbered = "\n\n---\n\n".join(
            f"Job {j+1}.\nTitle: {(t or '').strip() or '(none)'}\nDescription:\n{(d or '').strip()[:2000] or '(none)'}"
            for j, (t, d) in enumerate(batch)
        )
        prompt = f"""For each job below, extract only the technical skills and tools mentioned.
Return a JSON array of arrays: one array per job, in order. Example: [["Python","SQL"], ["AWS","Kafka"]].
No other text.

{numbered}"""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name=model_name)
            response = model.generate_content(prompt)
            if not response or not response.text:
                results.extend([[] for _ in batch])
                continue
            raw = response.text.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            arr = json.loads(raw)
            if isinstance(arr, list) and len(arr) >= len(batch):
                for k in range(len(batch)):
                    if k < len(arr) and isinstance(arr[k], list):
                        results.append([str(x).strip() for x in arr[k] if x and str(x).strip()])
                    else:
                        results.append([])
            else:
                results.extend([[] for _ in batch])
        except Exception as e:
            logger.warning("Gemini batch skills extraction failed for batch: %s", e)
            results.extend([[] for _ in batch])
    return results
