FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion/ ./ingestion/
COPY run_ingestion.py .
COPY scripts/ ./scripts/
COPY streamlit_app/ ./streamlit_app/

# Keep container running for exec
CMD ["tail", "-f", "/dev/null"]
