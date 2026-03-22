"""GCS bucket env validation (load errors / Terraform paste mistakes)."""
from ingestion.config import gcs_bucket_config_error, normalize_gcs_bucket


def test_normalize_strips_gs_prefix() -> None:
    assert normalize_gcs_bucket("gs://my-bucket/raw") == "my-bucket"


def test_rejects_terraform_warning_blob() -> None:
    bad = "╷\n│ Warning: No outputs found\n╵"
    assert gcs_bucket_config_error(bad) is not None


def test_rejects_multiline() -> None:
    assert gcs_bucket_config_error("my-bucket\noops") is not None


def test_accepts_plausible_bucket() -> None:
    assert gcs_bucket_config_error("my-project-raw-bucket-123") is None
