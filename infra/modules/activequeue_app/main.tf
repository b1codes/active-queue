terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# Service Account with least-privilege roles per SPEC §10.5: roles/datastore.user is its
# only project-level role. Secret access is granted per secret, below.
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

# The API reads only the YouTube key. The OAuth client secrets are Identity Platform's,
# not the API's, so a project-wide secretAccessor grant would over-share them.
resource "google_secret_manager_secret_iam_member" "api_reads_youtube_key" {
  project   = var.gcp_project_id
  secret_id = google_secret_manager_secret.youtube_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api_sa.email}"
}

# Signs the Firebase custom token for the post-deploy smoke check
# (scripts/smoke_test.py). It holds no roles; the members in var.smoke_test_signers may
# sign JWTs as it.
resource "google_service_account" "smoke_test" {
  account_id   = "activequeue-smoke-${var.env}"
  display_name = "ActiveQueue post-deploy smoke test (${var.env})"
  project      = var.gcp_project_id
}

resource "google_service_account_iam_member" "smoke_test_signers" {
  for_each           = toset(var.smoke_test_signers)
  service_account_id = google_service_account.smoke_test.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = each.value
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
      # An immutable image reference from scripts/deploy.sh (digest of the CI-passed
      # commit's build). There is no default, so a placeholder can't be deployed.
      image = var.container_image

      # A revision becomes ready only once /healthz reads Firestore, so a broken image or
      # missing permission never takes traffic from the serving revision. Cloud Run
      # probes reach the container directly; the reserved-path rule (SPEC §9.8) doesn't
      # apply. There is deliberately no liveness probe on /healthz: a Firestore outage
      # would then restart every instance.
      startup_probe {
        initial_delay_seconds = 0
        period_seconds        = 3
        timeout_seconds       = 2
        failure_threshold     = 20
        http_get {
          path = "/healthz"
          port = 8080
        }
      }

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

      # Cloud Run's front end appends the caller's address to X-Forwarded-For; trust
      # exactly that one hop for the per-IP rate-limit guard (client-supplied entries
      # to its left are ignored).
      env {
        name  = "TRUSTED_PROXY_HOPS"
        value = "1"
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

# The app calls the API directly with a Firebase ID token, which the API verifies itself.
# Without a public invoker, Cloud Run's IAM check returns 403 to every app request.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.gcp_project_id
  location = google_cloud_run_v2_service.api_service.location
  name     = google_cloud_run_v2_service.api_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Identity Platform Configuration per SPEC §10.5 & house standard 007 §2
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
    var.custom_auth_domain,
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
