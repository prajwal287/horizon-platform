variable "project_id" {
  description = "GCP Project ID (set in terraform.tfvars; do not commit real tfvars)"
  type        = string

  validation {
    condition = (
      var.project_id == lower(var.project_id) &&
      length(var.project_id) >= 6 &&
      var.project_id != "your_gcp_project_id"
    )
    error_message = "Use your real GCP project ID: lowercase letters, digits, hyphens only (e.g. horizon-platform-488122). Replace the YOUR_GCP_PROJECT_ID placeholder from the example — never apply with the literal placeholder."
  }
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

variable "enable_pipeline_scheduler" {
  description = "If true, create a daily Cloud Scheduler job that publishes a tick to the lakehouse Pub/Sub topic (subscriber required to run the pipeline)."
  type        = bool
  default     = false
}

variable "pipeline_scheduler_cron" {
  description = "Cron for pipeline signal (default 06:00 daily)."
  type        = string
  default     = "0 6 * * *"
}

variable "pipeline_scheduler_timezone" {
  description = "Time zone for Cloud Scheduler"
  type        = string
  default     = "America/New_York"
}

variable "pipeline_scheduler_region" {
  description = "Region for Cloud Scheduler job resource"
  type        = string
  default     = "us-central1"
}

# -----------------------------------------------------------------------------
# Streamlit on Cloud Run (optional)
# -----------------------------------------------------------------------------

variable "enable_streamlit_cloud_run" {
  description = "If true, create Artifact Registry repo, Cloud Run v2 service, and SA with BigQuery read access for the Streamlit dashboard."
  type        = bool
  default     = false
}

variable "streamlit_cloud_run_service_name" {
  description = "Cloud Run service name (must be unique per region)."
  type        = string
  default     = "horizon-streamlit"
}

variable "streamlit_service_account_id" {
  description = "GCP service account account_id (6–30 chars) for the Cloud Run revision (not the default compute SA)."
  type        = string
  default     = "horizon-streamlit-cr"
}

variable "streamlit_artifact_registry_repo" {
  description = "Artifact Registry Docker repository id for Streamlit images."
  type        = string
  default     = "horizon-streamlit"
}

variable "streamlit_image_name" {
  description = "Docker image name inside the Artifact Registry repo (without tag)."
  type        = string
  default     = "dashboard"
}

variable "streamlit_image_tag" {
  description = "Docker image tag when streamlit_container_image is unset."
  type        = string
  default     = "latest"
}

variable "streamlit_container_image" {
  description = "Full container image URI (overrides region/project/repo/name/tag). Must exist in Artifact Registry before terraform apply can succeed."
  type        = string
  default     = ""
}

variable "streamlit_ingress_all" {
  description = "If true, INGRESS_TRAFFIC_ALL (public URL). If false, INGRESS_TRAFFIC_INTERNAL_ONLY (VPC / internal access patterns)."
  type        = bool
  default     = true
}

variable "streamlit_allow_unauthenticated" {
  description = "If true, grant roles/run.invoker to allUsers (only meaningful when streamlit_ingress_all is true)."
  type        = bool
  default     = true
}

variable "streamlit_min_instances" {
  description = "Cloud Run min instances (0 allows scale-to-zero)."
  type        = number
  default     = 0
}

variable "streamlit_max_instances" {
  description = "Cloud Run max instances."
  type        = number
  default     = 3
}

variable "streamlit_max_concurrency" {
  description = "Max concurrent requests per instance (Streamlit is single-user heavy; lower if sessions conflict)."
  type        = number
  default     = 40
}

variable "streamlit_request_timeout_seconds" {
  description = "Request timeout for the service (seconds)."
  type        = number
  default     = 300
}

variable "streamlit_cpu" {
  description = "CPU limit for the Streamlit container (e.g. 1 or 2)."
  type        = string
  default     = "1"
}

variable "streamlit_memory" {
  description = "Memory limit (e.g. 2Gi, 1Gi). Prefer 2Gi if OOM during cold start."
  type        = string
  default     = "2Gi"
}
