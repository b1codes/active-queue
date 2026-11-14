variable "gcp_project_id" {
  type        = string
  description = "GCP Project ID for Prod environment"
  default     = "activequeue-prod"
}

variable "gcp_region" {
  type        = string
  description = "GCP Region for Prod environment"
  default     = "us-central1"
}

# Set by scripts/deploy.sh: the digest of the image built from the CI-passed commit.
variable "container_image" {
  type        = string
  description = "Immutable API image reference (…/api@sha256:<digest>)"
}

# The OAuth credentials have no defaults: Identity Platform must never be configured with
# placeholders. scripts/deploy.sh reads them from TF_VAR_* or from Secret Manager.
variable "google_oauth_client_id" {
  type        = string
  description = "Google OAuth client ID for Prod"
}

variable "google_oauth_client_secret" {
  type        = string
  description = "Google OAuth client secret for Prod"
  sensitive   = true
}

variable "apple_services_id" {
  type        = string
  description = "Apple Services ID for Prod"
  default     = "com.activequeue.auth"
}

variable "apple_client_secret" {
  type        = string
  description = "Apple OAuth client secret (generated JWT) for Prod"
  sensitive   = true
}

variable "smoke_test_signers" {
  type        = list(string)
  description = "IAM members allowed to sign the post-deploy smoke test's custom token (e.g. [\"user:you@example.com\"])"
  default     = []
}
