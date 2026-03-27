#!/bin/sh
# Cloud Run sets PORT (default 8080). Local fallback 8501.
set -e
export PORT="${PORT:-8501}"
exec streamlit run streamlit_app/app.py \
  --server.address=0.0.0.0 \
  --server.port="$PORT" \
  --server.headless=true \
  --browser.gatherUsageStats=false
