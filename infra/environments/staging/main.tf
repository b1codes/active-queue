terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

variable "gcp_project_id" {
  type        = string
  description = "GCP Project ID for Staging environment"
  default     = "activequeue-staging"
}

variable "gcp_region" {
  type        = string
  description = "GCP Region for Staging environment"
  default     = "us-central1"
}

module "staging_app" {
  source = "../../modules/activequeue_app"

  gcp_project_id   = var.gcp_project_id
  gcp_region       = var.gcp_region
  env              = "staging"
  min_instances    = 0
  max_instances    = 10
  content_provider = "youtube"
}

output "cloud_run_url" {
  value = module.staging_app.cloud_run_url
}
