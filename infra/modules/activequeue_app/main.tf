terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Service Account with least-privilege roles per SPEC §10.5
resource "google_service_account" "api_sa" {
  account_id   = "activequeue-api-sa-${var.env}"
  display_name = "ActiveQueue API Service Account (${var.env})"
  project      = var.gcp_project_id
}

resource "google_project_iam_member" "datastore_user" {
  project = var.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.api_sa.email}"
}

resource "google_project_iam_member" "secret_accessor" {
  project = var.gcp_project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api_sa.email}"
}

# Artifact Registry Repository per SPEC §10.5
resource "google_artifact_registry_repository" "api_repo" {
  provider      = google
  project       = var.gcp_project_id
  location      = var.gcp_region
  repository_id = "activequeue-api-${var.env}"
  description   = "Docker repository for ActiveQueue API images (${var.env})"
  format        = "DOCKER"
}

# Firestore Database in Native mode per SPEC §10.5
resource "google_firestore_database" "database" {
  project     = var.gcp_project_id
  name        = "(default)"
  location_id = var.gcp_region
  type        = "FIRESTORE_NATIVE"
}

# Secret Manager for YouTube API Key per SPEC §10.5
resource "google_secret_manager_secret" "youtube_api_key" {
  project   = var.gcp_project_id
  secret_id = "youtube-api-key-${var.env}"

  replication {
    auto {}
  }
}

# Secret Manager for Google OAuth Client Secret per house standard 007 §2
resource "google_secret_manager_secret" "google_oauth_client_secret" {
  project   = var.gcp_project_id
  secret_id = "google-oauth-client-secret-${var.env}"

  replication {
    auto {}
  }
}

# Secret Manager for Apple OAuth Client Secret per house standard 007 §2
resource "google_secret_manager_secret" "apple_oauth_client_secret" {
  project   = var.gcp_project_id
  secret_id = "apple-oauth-client-secret-${var.env}"

  replication {
    auto {}
  }
}

# Cloud Run v2 Service per SPEC §10.5
resource "google_cloud_run_v2_service" "api_service" {
  name     = "activequeue-api-${var.env}"
  location = var.gcp_region
  project  = var.gcp_project_id

  template {
    service_account = google_service_account.api_sa.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    max_instance_request_concurrency = 80

    containers {
      image = var.container_image

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }

      env {
        name  = "ENV"
        value = var.env
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.gcp_project_id
      }

      env {
        name  = "CONTENT_PROVIDER"
        value = var.content_provider
      }

      env {
        name = "YOUTUBE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.youtube_api_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }
}

# Identity Platform Configuration per SPEC §10.5
resource "google_identity_platform_config" "ic_config" {
  project = var.gcp_project_id

  sign_in {
    allow_duplicate_emails = false

    email {
      enabled           = true
      password_required = true
    }
  }

  authorized_domains = [
    "localhost",
    "activequeue.app",
    "${var.gcp_project_id}.firebaseapp.com",
  ]
}

# Google Provider IDP Config in Identity Platform
resource "google_identity_platform_default_supported_idp_config" "google_idp" {
  project       = var.gcp_project_id
  idp_id        = "google.com"
  client_id     = var.google_oauth_client_id
  client_secret = var.google_oauth_client_secret
  enabled       = true
}

# Apple Provider IDP Config in Identity Platform
resource "google_identity_platform_oauth_idp_config" "apple_idp" {
  name          = "apple.com"
  project       = var.gcp_project_id
  display_name  = "Apple"
  client_id     = var.apple_services_id
  issuer        = "https://appleid.apple.com"
  enabled       = true
  client_secret = var.apple_client_secret
}
