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
  description = "GCP Project ID for Prod environment"
  default     = "activequeue-prod"
}

variable "gcp_region" {
  type        = string
  description = "GCP Region for Prod environment"
  default     = "us-central1"
}

module "prod_app" {
  source = "../../modules/activequeue_app"

  gcp_project_id   = var.gcp_project_id
  gcp_region       = var.gcp_region
  env              = "prod"
  min_instances    = 1 # Min 1 instance in Prod to prevent 2-4s Python cold starts per SPEC §10.5
  max_instances    = 10
  content_provider = "youtube"
}

output "cloud_run_url" {
  value = module.prod_app.cloud_run_url
}
