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

module "staging_app" {
  source = "../../modules/activequeue_app"

  gcp_project_id   = var.gcp_project_id
  gcp_region       = var.gcp_region
  env              = "staging"
  container_image  = var.container_image
  min_instances    = 0 # Scale to zero between uses
  max_instances    = 10
  content_provider = "youtube"

  google_oauth_client_id     = var.google_oauth_client_id
  google_oauth_client_secret = var.google_oauth_client_secret
  apple_services_id          = var.apple_services_id
  apple_client_secret        = var.apple_client_secret
  smoke_test_signers         = var.smoke_test_signers
}
