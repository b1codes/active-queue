# ActiveQueue Infrastructure Configuration (Terraform)
# Deliberately executed with `fmt -check` and `validate` only until Milestone 6 (SPEC §12.5).
# `terraform plan` and `apply` are excluded until M6 to avoid requiring GCP credentials.

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
  description = "GCP Project ID"
  default     = "activequeue-local"
}

variable "gcp_region" {
  type        = string
  description = "GCP Region for Cloud Run & Firestore"
  default     = "us-central1"
}
