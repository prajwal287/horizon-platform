#!/usr/bin/env bash
# Phase 6 (EXECUTION_CHECKLIST): taxonomy skills for Kaggle Data Engineer 2023; optional Hugging Face (see below).
# Prerequisites: project root .venv activated (or PYTHON set), ADC (gcloud auth application-default login),
# GCS_BUCKET, GOOGLE_CLOUD_PROJECT, BIGQUERY_DATASET; Kaggle via KAGGLE_USERNAME+KAGGLE_KEY or ~/.kaggle/kaggle.json
# Optional: PHASE6_INCLUDE_HF=1 also re-ingests Hugging Face (uses job_type_skills + taxonomy when job_skills is null).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

: "${GCS_BUCKET:?Set GCS_BUCKET (e.g. in .env)}"
: "${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT}"

if [[ -z "${KAGGLE_USERNAME:-}" ]] || [[ -z "${KAGGLE_KEY:-${KAGGLE_API_TOKEN:-}}" ]]; then
  if [[ ! -f "${HOME}/.kaggle/kaggle.json" ]]; then
    echo "Kaggle auth required: set KAGGLE_USERNAME and KAGGLE_KEY (or KAGGLE_API_TOKEN), or place ~/.kaggle/kaggle.json" >&2
    exit 1
  fi
fi

export EXTRACT_SKILLS_TAXONOMY=1

PYTHON="${PYTHON:-python3}"
echo "==> Phase 6.1–6.2: ingest kaggle_data_engineer with taxonomy skills → GCS"
$PYTHON run_ingestion.py --source kaggle_data_engineer

echo "==> Phase 6.3: load Parquet → BigQuery raw_kaggle_data_engineer_2023"
$PYTHON scripts/load_gcs_to_bigquery.py --source kaggle_data_engineer

if [[ "${PHASE6_INCLUDE_HF:-}" == "1" ]]; then
  echo "==> Hugging Face: ingest with taxonomy on job_type_skills → GCS"
  $PYTHON run_ingestion.py --source huggingface
  echo "==> Hugging Face: load → BigQuery raw_huggingface_data_jobs"
  $PYTHON scripts/load_gcs_to_bigquery.py --source huggingface
fi

if [[ "${SKIP_MASTER:-}" == "1" ]]; then
  echo "==> Phase 6.4 skipped (SKIP_MASTER=1)"
else
  echo "==> Phase 6.4: rebuild master_jobs (clean view)"
  $PYTHON scripts/create_master_table.py --clean
fi

DS="${BIGQUERY_DATASET:-job_market_analysis}"
echo "Done. Spot-check: SELECT skills FROM \`$GOOGLE_CLOUD_PROJECT.$DS.raw_kaggle_data_engineer_2023\` WHERE skills IS NOT NULL LIMIT 10;"
