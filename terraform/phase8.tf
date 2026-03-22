# Phase 8: Secret Manager (pipeline secrets) + optional Cloud Scheduler → Pub/Sub tick.
# The scheduler only publishes a message; you still need a subscriber (e.g. Cloud Run, Workflows) to run ingest.

resource "google_project_service" "secretmanager" {
  project            = var.project_id
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_secret_manager_secret" "horizon_pipeline" {
  project   = var.project_id
  secret_id = "horizon-pipeline-secrets"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_iam_member" "lakehouse_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.horizon_pipeline.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.lakehouse.email}"
}

resource "google_project_service" "cloudscheduler" {
  count              = var.enable_pipeline_scheduler ? 1 : 0
  project            = var.project_id
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_cloud_scheduler_job" "horizon_pipeline_signal" {
  count    = var.enable_pipeline_scheduler ? 1 : 0
  name     = "horizon-daily-pipeline-signal"
  project  = var.project_id
  location = var.pipeline_scheduler_region

  schedule  = var.pipeline_scheduler_cron
  time_zone = var.pipeline_scheduler_timezone

  pubsub_target {
    topic_name = google_pubsub_topic.job_stream_input.id
    data       = base64encode(jsonencode({ kind = "horizon.scheduled.tick", version = 1 }))
  }

  depends_on = [google_project_service.cloudscheduler]
}
