"""Shared .env loading for repo CLIs and Streamlit (single implementation)."""
from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv_repo(*, override: bool = False, search_cwd: bool = False) -> None:
    """
    Load the first existing `.env` from repo root, then optionally cwd.

    - `override=False`: dotenv does not override existing env vars; manual fallback respects that.
    - `search_cwd=True`: also try `./.env` after repo root (matches run_ingestion behavior).
    """
    paths: list[Path] = [_REPO_ROOT / ".env"]
    if search_cwd:
        paths.append(Path.cwd() / ".env")

    for path in paths:
        if not path.is_file():
            continue
        try:
            from dotenv import load_dotenv

            load_dotenv(path, override=override)
            return
        except ImportError:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, _, v = line.partition("=")
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k and v and (override or k not in os.environ):
                            os.environ[k] = v
            return
