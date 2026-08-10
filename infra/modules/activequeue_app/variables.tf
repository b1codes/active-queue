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

variable "custom_auth_domain" {
  type        = string
  description = "Shared custom auth domain for Sign in with Apple and Google per house standard 007 §2"
  default     = "auth.activequeue.app"
}

variable "google_oauth_client_id" {
  type        = string
  description = "Environment-specific Google OAuth Client ID"
  default     = "dummy-google-client-id.apps.googleusercontent.com"
}

variable "google_oauth_client_secret" {
  type        = string
  description = "Environment-specific Google OAuth Client Secret"
  default     = "dummy-google-client-secret"
  sensitive   = true
}

variable "apple_services_id" {
  type        = string
  description = "Environment-specific Apple Services ID"
  default     = "com.activequeue.auth"
}

variable "apple_team_id" {
  type        = string
  description = "Apple Developer Team ID"
  default     = "ABC123XYZ8"
}

variable "apple_key_id" {
  type        = string
  description = "Apple OAuth Key ID"
  default     = "KEY123XYZ8"
}

variable "apple_client_secret" {
  type        = string
  description = "Apple OAuth Client Secret / Generated JWT"
  default     = "dummy-apple-client-secret"
  sensitive   = true
}
