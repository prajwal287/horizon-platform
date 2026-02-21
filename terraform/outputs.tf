output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "project_name" {
  description = "GCP project display name"
  value       = var.project_name
}

output "gcs_bucket_name" {
  description = "Name of the GCS raw bucket"
  value       = google_storage_bucket.raw.name
}

output "gcs_bucket_uri" {
  description = "URI of the GCS raw bucket"
  value       = google_storage_bucket.raw.url
}

output "bigquery_dataset_id" {
  description = "BigQuery dataset ID for job market analysis"
  value       = google_bigquery_dataset.job_market_analysis.dataset_id
}

output "bigquery_dataset_full_id" {
  description = "Fully qualified BigQuery dataset ID"
  value       = google_bigquery_dataset.job_market_analysis.id
}

output "pubsub_topic_name" {
  description = "Pub/Sub topic name for real-time ingestion"
  value       = google_pubsub_topic.job_stream_input.name
}

output "pubsub_topic_id" {
  description = "Full Pub/Sub topic ID"
  value       = google_pubsub_topic.job_stream_input.id
}

output "service_account_email" {
  description = "Email of the lakehouse service account"
  value       = google_service_account.lakehouse.email
}
