variable "gcp_project_id" {
  type        = string
  description = "GCP Project ID"
}

variable "gcp_region" {
  type        = string
  description = "GCP Region"
  default     = "us-central1"
}

variable "env" {
  type        = string
  description = "Environment (dev, staging, prod)"
}

variable "container_image" {
  type        = string
  description = "Docker image URI for Cloud Run"
  default     = "us-central1-docker.pkg.dev/activequeue-local/activequeue-api/api:latest"
}

variable "min_instances" {
  type        = number
  description = "Minimum Cloud Run instances (0 for dev/staging, 1 for prod)"
  default     = 0
}

variable "max_instances" {
  type        = number
  description = "Maximum Cloud Run instances"
  default     = 10
}

variable "content_provider" {
  type        = string
  description = "Content provider mode (fixture or youtube)"
  default     = "youtube"
}
