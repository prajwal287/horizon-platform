# Host the Streamlit app on GCP

The usual pattern is **Cloud Run**: HTTPS URL, pay per request, no servers to patch. The container runs Streamlit; **BigQuery** is called with the **Cloud Run service account** (no `gcloud` login inside the container).

---

## 0. Terraform (recommended)

The repo includes **`terraform/streamlit.tf`**: Artifact Registry (Docker), dedicated service account, `roles/bigquery.jobUser` + dataset **`roles/bigquery.dataViewer`**, and a **Cloud Run v2** service.

1. **Image must exist** in Artifact Registry before `apply` can succeed (Cloud Run validates the image). From **repo root**, with `REGION` and `PROJECT_ID` matching `terraform.tfvars`:

   ```bash
   export REGION=us-central1
   export PROJECT_ID=your-project-id
   export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/horizon-streamlit/dashboard:latest"

   gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

   docker build -f Dockerfile.streamlit -t "${IMAGE}" .
   docker push "${IMAGE}"
   ```

   (Default repo/image names match `streamlit_artifact_registry_repo` = `horizon-streamlit` and `streamlit_image_name` = `dashboard`.)

2. **Enable** in `terraform/terraform.tfvars`:

   ```hcl
   enable_streamlit_cloud_run = true
   ```

3. **Apply**:

   ```bash
   cd terraform
   terraform init
   terraform apply
   ```

4. **Outputs**: `streamlit_service_uri` (app URL), `streamlit_cloudrun_service_account_email`, `streamlit_image_uri`.

**Flags:** `streamlit_allow_unauthenticated` (default `true`) and `streamlit_ingress_all` (default `true`). For private access, set `streamlit_allow_unauthenticated = false`, `streamlit_ingress_all` per your networking needs, and grant **`roles/run.invoker`** to users or groups.

**If `apply` fails** on Cloud Run with an image error, confirm `docker push` succeeded and the URI matches `terraform plan` (see variable defaults or set `streamlit_container_image`).

---

## 1. What you need

- **GCP project** with **Artifact Registry** (Docker) and **Cloud Run API** enabled.
- A **BigQuery dataset** your users will query (e.g. `job_market_analysis`).
- **IAM**: the identity that runs Cloud Run must be allowed to run queries and read tables (see §4).

---

## 2. Build the Streamlit image

From the **repo root**, use the slim **`Dockerfile.streamlit`** (Streamlit + `streamlit_app/` only):

```bash
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1
export REPO=horizon-docker
export IMAGE=streamlit-dashboard

gcloud services enable artifactregistry.googleapis.com run.googleapis.com cloudbuild.googleapis.com --project=$PROJECT_ID

gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION --project=$PROJECT_ID 2>/dev/null || true

gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

docker build -f Dockerfile.streamlit -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE}:latest .

docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE}:latest
```

(You can use **Cloud Build** instead of local `docker build`; the image URI stays the same.)

---

## 3. Deploy to Cloud Run

Cloud Run injects **`PORT`**; the entrypoint runs Streamlit on that port (see `streamlit_app/entrypoint_cloud_run.sh`).

```bash
export SERVICE=horizon-streamlit

gcloud run deploy $SERVICE \
  --project=$PROJECT_ID \
  --region=$REGION \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE}:latest \
  --platform=managed \
  --allow-unauthenticated \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID,BIGQUERY_DATASET=job_market_analysis \
  --service-account=YOUR_RUN_SERVICE_ACCOUNT@${PROJECT_ID}.iam.gserviceaccount.com
```

- Remove **`--allow-unauthenticated`** if you want **only signed-in GCP users** or **IAM** (then use “Require authentication” and grant `roles/run.invoker`).
- Change **`BIGQUERY_DATASET`** if your lakehouse dataset name differs.

After deploy, `gcloud run services describe` prints the **HTTPS URL**.

---

## 4. IAM (BigQuery access for Cloud Run)

The **`--service-account`** above must be able to read the tables/views the app queries (`master_jobs`, `raw_*`, etc.).

Typical roles (tune to least privilege):

| Role | Why |
|------|-----|
| `roles/bigquery.jobUser` | Run query jobs in the project |
| `roles/bigquery.dataViewer` | Read table data (project-wide or per dataset) |

**Least privilege (dataset-level):** grant **`READER`** (or custom) on `job_market_analysis` to that service account in BigQuery/IAM.

**Do not** bake JSON key files into the image; use the **Cloud Run service account** only.

---

## 5. Environment variables

The app reads **`GOOGLE_CLOUD_PROJECT`** and **`BIGQUERY_DATASET`** (see `streamlit_app/app.py`). Set both on Cloud Run as in §3.

Optional: **`HF_TOKEN`** is **not** required for the dashboard (only for ingestion). **`GCS_BUCKET`** is not required unless you extend the app to touch GCS.

---

## 6. Alternatives (when to use what)

| Option | When |
|--------|------|
| **Cloud Run** | Default: serverless, scales to zero, good for internal dashboards with IAM. |
| **GKE / GCE** | Long-lived VMs, custom networking, or sidecars — more ops effort. |
| **App Engine Flex** | Legacy path; Cloud Run is simpler for containers. |

---

## 7. Local dry-run of the production image

Simulate Cloud Run’s port and (if you want) ADC:

```bash
docker build -f Dockerfile.streamlit -t horizon-streamlit:local .

docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e GOOGLE_CLOUD_PROJECT=$PROJECT_ID \
  -e BIGQUERY_DATASET=job_market_analysis \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  horizon-streamlit:local
```

Open **http://localhost:8080**. On Cloud Run you omit the volume; identity comes from the **service account**.

---

## 8. Operations notes

- **Cold start**: first request after idle may take a few seconds.
- **Concurrency**: Streamlit is single-process; cap **`--max-instances`** and/or **`--concurrency=1`** if you see contention (trade cost vs parallelism).
- **Secrets**: prefer **Secret Manager** + `--set-secrets` for any future API keys, not plaintext env for sensitive values.

---

## Related

- [STREAMLIT_TESTING.md](STREAMLIT_TESTING.md) — local and Docker Compose testing.
- [README.md](../README.md) — Streamlit quick start.
