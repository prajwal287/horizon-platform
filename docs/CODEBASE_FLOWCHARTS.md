# Horizon – Mermaid Flowcharts

Use these in GitHub, VS Code (with a Mermaid extension), or any Markdown viewer that supports Mermaid.

---

## End-to-end flow

```mermaid
flowchart LR
    subgraph YourLaptop["Your laptop"]
        ENV[".env\n(project, bucket, Kaggle)"]
        GCLOUD["~/.config/gcloud\n(ADC JSON)"]
        DOCKER["Docker container"]
    end

    subgraph External["External"]
        HF["Hugging Face API"]
        KAG["Kaggle API"]
    end

    subgraph GCP["Google Cloud"]
        GCS["GCS bucket\n(Parquet files)"]
    end

    ENV --> DOCKER
    GCLOUD --> DOCKER
    DOCKER --> HF
    DOCKER --> KAG
    DOCKER -->|"dlt writes Parquet"| GCS
```

---

## run_ingestion.py decision flow

```mermaid
flowchart TD
    A[Start run_ingestion.py] --> B[Parse --source]
    B --> C{GCS_BUCKET set?}
    C -->|No| D[Error, exit]
    C -->|Yes| E{source == all?}
    E -->|Yes| F[Run all 4 pipelines]
    E -->|No| G[Run single pipeline]
    F --> H[huggingface, kaggle_data_engineer,\nkaggle_linkedin, kaggle_linkedin_skills]
    G --> I[Run chosen one]
    H --> J[End]
    I --> J
```

---

## Single pipeline (e.g. Kaggle Data Engineer)

```mermaid
flowchart TD
    A[run_kaggle_data_engineer.run] --> B[run_pipeline in common.py]
    B --> C[get_gcs_base_url]
    C --> D[Set DESTINATION__FILESYSTEM__BUCKET_URL]
    D --> E[dlt.pipeline destination=filesystem]
    E --> F[pipeline.run with jobs_resource]
    F --> G[jobs_resource: stream_kaggle_data_engineer_2023]
    G --> H[Download Kaggle dataset to /app/data]
    H --> I[Read CSV in chunks, filter, yield rows]
    I --> J[dlt writes Parquet to GCS]
    J --> K[Return pipeline]
```

---

## Where secrets live (local → container)

```mermaid
flowchart LR
    subgraph Host["Your computer"]
        ADC["~/.config/gcloud/\napplication_default_credentials.json"]
        ENV[".env\nGOOGLE_CLOUD_PROJECT\nGCS_BUCKET\nKAGGLE_USERNAME\nKAGGLE_KEY"]
        DATA["./data"]
        SEC["./secrets"]
    end

    subgraph Container["Docker container"]
        G["/app/gcloud (ro)"]
        E2["Env vars"]
        D2["/app/data"]
        S2["/app/secrets"]
    end

    ADC -->|volume mount| G
    ENV -->|env_file + environment| E2
    DATA -->|volume mount| D2
    SEC -->|volume mount| S2
```

---

## Docker build and run

```mermaid
flowchart TD
    A[docker compose build] --> B[Dockerfile: Python + deps + code]
    B --> C[Image: app]
    C --> D[docker compose run --rm app python run_ingestion.py ...]
    D --> E[Mount .env, ~/.config/gcloud, ./data, ./secrets]
    E --> F[Run command in container]
    F --> G[Container exits, removed]
```
