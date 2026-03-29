# -----------------------------------------------------------------------------
# Streamlit dashboard on Cloud Run + Artifact Registry (optional)
# Set enable_streamlit_cloud_run = true in terraform.tfvars after you can push an image.
# Image must exist before apply succeeds: see output streamlit_image_uri and docs/STREAMLIT_HOSTING_GCP.md
# -----------------------------------------------------------------------------

locals {
  streamlit_image_effective = var.streamlit_container_image != "" ? var.streamlit_container_image : "${var.region}-docker.pkg.dev/${var.project_id}/${var.streamlit_artifact_registry_repo}/${var.streamlit_image_name}:${var.streamlit_image_tag}"
}

resource "google_project_service" "artifactregistry_streamlit" {
  count              = var.enable_streamlit_cloud_run ? 1 : 0
  project            = var.project_id
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudrun_streamlit" {
  count              = var.enable_streamlit_cloud_run ? 1 : 0
  project            = var.project_id
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "streamlit" {
  count         = var.enable_streamlit_cloud_run ? 1 : 0
  location      = var.region
  repository_id = var.streamlit_artifact_registry_repo
  description   = "Horizon Streamlit dashboard (Docker)"
  format        = "DOCKER"

  depends_on = [google_project_service.artifactregistry_streamlit]
}

resource "google_service_account" "streamlit_cloudrun" {
  count        = var.enable_streamlit_cloud_run ? 1 : 0
  account_id   = var.streamlit_service_account_id
  display_name = "Horizon Streamlit Cloud Run"
  project      = var.project_id
}

resource "google_project_iam_member" "streamlit_bigquery_job_user" {
  count   = var.enable_streamlit_cloud_run ? 1 : 0
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.streamlit_cloudrun[0].email}"
}

resource "google_bigquery_dataset_iam_member" "streamlit_bq_data_viewer" {
  count      = var.enable_streamlit_cloud_run ? 1 : 0
  project    = var.project_id
  dataset_id = google_bigquery_dataset.job_market_analysis.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.streamlit_cloudrun[0].email}"
}

resource "google_cloud_run_v2_service" "streamlit" {
  count    = var.enable_streamlit_cloud_run ? 1 : 0
  name     = var.streamlit_cloud_run_service_name
  location = var.region
  project  = var.project_id

  ingress = var.streamlit_ingress_all ? "INGRESS_TRAFFIC_ALL" : "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account                  = google_service_account.streamlit_cloudrun[0].email
    max_instance_request_concurrency = var.streamlit_max_concurrency
    timeout                          = "${var.streamlit_request_timeout_seconds}s"

    scaling {
      min_instance_count = var.streamlit_min_instances
      max_instance_count = var.streamlit_max_instances
    }

    containers {
      image = local.streamlit_image_effective
      ports {
        container_port = 8080
      }
      # Streamlit can take longer than default startup probing; avoid false "port not listening" failures.
      startup_probe {
        initial_delay_seconds = 10
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 30
        tcp_socket {
          port = 8080
        }
      }
      resources {
        limits = {
          cpu    = var.streamlit_cpu
          memory = var.streamlit_memory
        }
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "BIGQUERY_DATASET"
        value = var.bigquery_dataset_id
      }
    }
  }

  depends_on = [
    google_project_service.cloudrun_streamlit,
    google_artifact_registry_repository.streamlit,
    google_project_iam_member.streamlit_bigquery_job_user,
    google_bigquery_dataset_iam_member.streamlit_bq_data_viewer,
  ]
}

# Public HTTPS URL (set streamlit_ingress_all true and allow unauthenticated invoker).
resource "google_cloud_run_v2_service_iam_member" "streamlit_invoker_public" {
  count    = var.enable_streamlit_cloud_run && var.streamlit_allow_unauthenticated && var.streamlit_ingress_all ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.streamlit[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

