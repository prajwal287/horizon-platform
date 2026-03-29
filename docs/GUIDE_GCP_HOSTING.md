# Hosting on GCP (Cloud Run, ingress, IAM)

This guide explains **how Horizon’s Streamlit dashboard is hosted on GCP**, why **ingress** matters, and how pieces fit together. Terraform in this repo can provision the same pattern under `terraform/streamlit.tf`.

**Your live URL after apply:** `terraform -chdir=terraform output -raw streamlit_service_uri` (from repo root). Root **[README.md](../README.md)** also lists an **example** Cloud Run URL and a summary of how the project meets common data-engineering criteria.

---

## Why Cloud Run?

- **Serverless containers:** you deploy an image; Google runs it and scales to zero when idle.
- **HTTPS URL** without managing VMs or Kubernetes for a simple internal dashboard.
- **Identity:** the container uses a **service account** to call BigQuery—no user `gcloud login` inside the container.

---

## What “ingress” means (important)

**Ingress** controls **who can reach** your Cloud Run service **at the network edge** (before IAM).

| Setting (concept) | Meaning |
|-------------------|---------|
| **All traffic (public)** | Anyone on the internet can **try** to open the HTTPS URL. Whether they **succeed** still depends on **IAM** (`roles/run.invoker`) if you require authentication. |
| **Internal / VPC** | Only traffic from your VPC or Google’s internal surface can hit the service—good for private apps. |

In this repo’s Terraform (`streamlit.tf`), **`streamlit_ingress_all`** maps to Cloud Run v2 **INGRESS_TRAFFIC_ALL** vs **INGRESS_TRAFFIC_INTERNAL_ONLY** — public route vs internal-only route.

**Why it matters**

- A **public ingress + allow unauthenticated** dashboard is easy to demo but **must not** leak secrets in the UI (env vars with API keys, printed project details).
- A **private ingress** reduces scan noise but requires VPN/peering or a load balancer path for humans to access it.

Pair ingress with:

- **`streamlit_allow_unauthenticated`**: if `false`, callers need **`roles/run.invoker`** (users, groups, or service accounts) even if ingress is public.

---

## Recommended path in this repo (Terraform + Artifact Registry)

1. **Build and push** the Streamlit image (**Cloud Run requires `linux/amd64`**; Apple Silicon: use `buildx`):

```bash
cd /path/to/repo-root
export REGION=us-central1
export PROJECT_ID=YOUR_GCP_PROJECT_ID
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/horizon-streamlit/dashboard:latest"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  -f Dockerfile.streamlit \
  -t "${IMAGE}" \
  --push .
```

2. **Enable Streamlit** in `terraform/terraform.tfvars`:

```hcl
enable_streamlit_cloud_run      = true
streamlit_allow_unauthenticated = true   # false for IAP / IAM-only
streamlit_ingress_all          = true   # false for internal-only
```

3. **Apply**

```bash
cd terraform
terraform apply
terraform output streamlit_service_uri
```

4. **IAM for BigQuery** — Terraform attaches **`bigquery.jobUser`** and **`dataViewer`** on the **landing dataset** (`job_market_analysis`) to the Cloud Run service account. dbt gold datasets are **not** required for the default Streamlit explorer (it uses `master_jobs` / `raw_*`).

---

## Shell script entrypoint and `PORT`

Cloud Run sets **`PORT`** (often `8080`). The image runs `streamlit_app/entrypoint_cloud_run.sh`, which binds Streamlit to `$PORT`. If the container listens on the wrong port, health checks fail and the revision never serves traffic.

---

## Alternative: `gcloud run deploy`

If you are not using Terraform for Cloud Run: build an image to Artifact Registry, then:

```bash
gcloud run deploy horizon-streamlit \
  --project=YOUR_GCP_PROJECT_ID \
  --region=$REGION \
  --image=$IMAGE \
  --platform=managed \
  --allow-unauthenticated \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=YOUR_GCP_PROJECT_ID,BIGQUERY_DATASET=job_market_analysis \
  --service-account=YOUR_STREAMLIT_SA@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com
```

The service account needs BigQuery job + read access to the dataset you query.

---

## Local testing of the production image

```bash
docker build -f Dockerfile.streamlit -t horizon-streamlit:local .
docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e GOOGLE_CLOUD_PROJECT=YOUR_GCP_PROJECT_ID \
  -e BIGQUERY_DATASET=job_market_analysis \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  horizon-streamlit:local
```

Open http://localhost:8080 . On Cloud Run, drop the volume—use the **service account** only.

---

## Common failures

| Error | Typical fix |
|-------|-------------|
| Image `amd64/linux` / OCI index | Rebuild with `--platform linux/amd64` and `--provenance=false --sbom=false` + `buildx --push`. |
| Entrypoint “no such file” | CRLF in shell script or wrong `WORKDIR`; Dockerfile normalizes line endings. |
| BigQuery permission denied | Grant **`roles/bigquery.dataViewer`** (and **`jobUser`**) on the dataset to the Cloud Run SA. |
| 403 on URL | Add **`roles/run.invoker`** for authenticated mode; or redeploy with unauthenticated if policy allows. |

---

## Terraform vs “just console”

- **Terraform:** repeatable, reviewable in PRs, same stack in dev/stage/prod.
- **Console / gcloud only:** fine for a one-off demo; harder to reproduce and audit.

This project uses Terraform for the **data plane** (bucket, BigQuery, Pub/Sub, SA) and **optional** Streamlit Cloud Run so the environment stays reproducible.
