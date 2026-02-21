variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "horizon-platform-488122"
}

variable "project_name" {
  description = "GCP project display name (used for labels)"
  type        = string
  default     = "Horizon-platform"
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "gcs_bucket_name" {
  description = "Name of the GCS bucket for raw data"
  type        = string
  default     = "job-lakehouse-raw"
}

variable "bigquery_dataset_id" {
  description = "BigQuery dataset ID for job market analysis"
  type        = string
  default     = "job_market_analysis"
}

variable "pubsub_topic_name" {
  description = "Pub/Sub topic name for real-time ingestion"
  type        = string
  default     = "job-stream-input"
}

variable "service_account_name" {
  description = "Name of the service account for lakehouse workloads"
  type        = string
  default     = "lakehouse-sa"
}

variable "lifecycle_nearline_days" {
  description = "Days after which GCS objects move to Nearline storage class"
  type        = number
  default     = 90
}
