terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# GCS Bucket - Raw data landing (Standard, lifecycle to Nearline after 90 days)
# ---------------------------------------------------------------------------
resource "google_storage_bucket" "raw" {
  name     = "${var.project_id}-${var.gcs_bucket_name}"
  location = var.region
  storage_class = "STANDARD"

  lifecycle_rule {
    condition {
      age = var.lifecycle_nearline_days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  labels = {
    project = lower(var.project_name)
  }

  uniform_bucket_level_access = true
}

# ---------------------------------------------------------------------------
# BigQuery Dataset - Job market analysis
# ---------------------------------------------------------------------------
resource "google_bigquery_dataset" "job_market_analysis" {
  dataset_id = var.bigquery_dataset_id
  location   = var.region
  project    = var.project_id

  labels = {
    project = lower(var.project_name)
  }
}

# ---------------------------------------------------------------------------
# Pub/Sub Topic - Real-time ingestion
# ---------------------------------------------------------------------------
resource "google_pubsub_topic" "job_stream_input" {
  name    = var.pubsub_topic_name
  project = var.project_id

  labels = {
    project = lower(var.project_name)
  }
}

# ---------------------------------------------------------------------------
# Service Account - Lakehouse workloads
# ---------------------------------------------------------------------------
resource "google_service_account" "lakehouse" {
  account_id   = var.service_account_name
  display_name = "Lakehouse Service Account"
  project      = var.project_id
}

# Storage Object Admin on the raw bucket
resource "google_storage_bucket_iam_member" "lakehouse_storage_admin" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.lakehouse.email}"
}

# BigQuery Admin (project-level for dataset access)
resource "google_project_iam_member" "lakehouse_bigquery_admin" {
  project = var.project_id
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${google_service_account.lakehouse.email}"
}

# Pub/Sub Publisher on the topic
resource "google_pubsub_topic_iam_member" "lakehouse_pubsub_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.job_stream_input.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.lakehouse.email}"
}
