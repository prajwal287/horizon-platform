"""Shared Kaggle API download: unzip into data/kaggle/<slug>/."""
import logging
import os
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi

logger = logging.getLogger(__name__)

# Default base dir for Kaggle downloads (mount point in Docker: /app/data)
KAGGLE_BASE = os.environ.get("KAGGLE_DATA_PATH", os.path.join(os.getcwd(), "data", "kaggle"))


def ensure_kaggle_credentials() -> None:
    """Raise if KAGGLE_USERNAME or KAGGLE_KEY are missing. Accepts KAGGLE_API_TOKEN as alias for KAGGLE_KEY."""
    if not os.environ.get("KAGGLE_KEY") and os.environ.get("KAGGLE_API_TOKEN"):
        os.environ["KAGGLE_KEY"] = os.environ["KAGGLE_API_TOKEN"]
    if not os.environ.get("KAGGLE_USERNAME") or not os.environ.get("KAGGLE_KEY"):
        raise ValueError(
            "KAGGLE_USERNAME and KAGGLE_KEY (or KAGGLE_API_TOKEN) environment variables are required for Kaggle pipelines. "
            "Set them in .env or export before running."
        )


def download_dataset(dataset: str, path: str | None = None, unzip: bool = True) -> Path:
    """
    Download a Kaggle dataset (e.g. 'lukkardata/data-engineer-job-postings-2023').
    Saves to KAGGLE_BASE/<slug>/ or path if given. Returns the directory path.
    """
    ensure_kaggle_credentials()
    slug = dataset.replace("/", "-")
    dest = path or os.path.join(KAGGLE_BASE, slug)
    os.makedirs(dest, exist_ok=True)
    api = KaggleApi()
    api.authenticate()
    logger.info("Downloading Kaggle dataset %s to %s", dataset, dest)
    api.dataset_download_files(dataset, path=dest, unzip=unzip, quiet=False)
    return Path(dest)
