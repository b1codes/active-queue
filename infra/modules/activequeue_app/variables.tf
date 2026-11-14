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
  description = "Immutable image reference for Cloud Run (registry/api@sha256:...), set by scripts/deploy.sh"

  validation {
    condition     = can(regex("@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "container_image must be pinned by digest (…/api@sha256:<digest>), not a mutable tag such as :latest."
  }
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
}

variable "google_oauth_client_secret" {
  type        = string
  description = "Environment-specific Google OAuth Client Secret"
  sensitive   = true
}

variable "apple_services_id" {
  type        = string
  description = "Environment-specific Apple Services ID"
  default     = "com.activequeue.auth"
}

variable "apple_client_secret" {
  type        = string
  description = "Apple OAuth Client Secret / Generated JWT"
  sensitive   = true
}

variable "smoke_test_signers" {
  type        = list(string)
  description = "IAM members (user:… or serviceAccount:…) allowed to sign the post-deploy smoke test's custom token"
  default     = []
}
